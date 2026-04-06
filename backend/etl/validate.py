"""
PropRoo ETL Validation & Data Quality Script

Validates all output parquet files from the ETL pipeline before R2 upload.
Produces comprehensive data quality statistics and structured JSON reports.

Two-tier validation:
  Tier 1: Raw data quality (sales.parquet) — column completeness, uniqueness,
          value distributions, schema integrity, cross-column consistency.
  Tier 2: Derived data quality (growth, summaries, H3) — calculation
          reconciliation, referential integrity, aggregate consistency.

Exits with code 1 if any critical validation fails.
Optionally outputs JSON report to --output-dir for CI/CD artifact storage.
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Validation thresholds ──────────────────────────────────────────────────
MIN_GEOCODING_COVERAGE = 0.80  # 80%
MIN_CAGR = -0.5  # -50%
MAX_CAGR = 2.0  # +200%
MIN_CONTRACT_YEAR = 2000
MAX_CONTRACT_YEAR = 2026
RECONCILIATION_TOLERANCE = 0.01  # 1% tolerance for aggregate reconciliation


class ValidationError(Exception):
    """Raised when a critical validation check fails."""

    pass


# ── Data Profiling Helpers ─────────────────────────────────────────────────


def profile_column(series: pd.Series) -> dict[str, Any]:
    """Generate comprehensive statistics for a single column."""
    total = len(series)
    null_count = int(series.isna().sum())
    null_pct = round(null_count / total * 100, 2) if total > 0 else 0.0
    non_null = total - null_count

    profile: dict[str, Any] = {
        "dtype": str(series.dtype),
        "total_rows": total,
        "null_count": null_count,
        "null_pct": null_pct,
        "non_null_count": non_null,
        "completeness_pct": round(100 - null_pct, 2),
    }

    if non_null == 0:
        profile["status"] = "EMPTY"
        return profile

    # Numeric columns
    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(series, errors="coerce").dropna()
        if len(numeric) > 0:
            profile.update(
                {
                    "kind": "numeric",
                    "min": float(numeric.min()),
                    "max": float(numeric.max()),
                    "mean": round(float(numeric.mean()), 4),
                    "median": round(float(numeric.median()), 4),
                    "std": round(float(numeric.std()), 4) if len(numeric) > 1 else 0.0,
                    "unique_count": int(numeric.nunique()),
                    "unique_pct": round(numeric.nunique() / len(numeric) * 100, 2),
                    "zero_count": int((numeric == 0).sum()),
                    "negative_count": int((numeric < 0).sum()),
                    "positive_count": int((numeric > 0).sum()),
                }
            )
            # Percentiles
            profile["percentiles"] = {
                "p25": round(float(numeric.quantile(0.25)), 4),
                "p50": round(float(numeric.quantile(0.50)), 4),
                "p75": round(float(numeric.quantile(0.75)), 4),
                "p90": round(float(numeric.quantile(0.90)), 4),
                "p95": round(float(numeric.quantile(0.95)), 4),
                "p99": round(float(numeric.quantile(0.99)), 4),
            }
        profile["status"] = "OK"

    # Datetime columns
    elif pd.api.types.is_datetime64_any_dtype(series):
        dt_series = series.dropna()
        if len(dt_series) > 0:
            profile.update(
                {
                    "kind": "datetime",
                    "min": str(dt_series.min()),
                    "max": str(dt_series.max()),
                    "unique_count": int(dt_series.nunique()),
                }
            )
        profile["status"] = "OK"

    # String / categorical columns
    else:
        str_series = series.dropna().astype(str)
        str_series = str_series[str_series != "nan"]
        if len(str_series) > 0:
            empty_count = int((str_series == "").sum())
            top_values = str_series.value_counts().head(10)
            profile.update(
                {
                    "kind": "string",
                    "unique_count": int(str_series.nunique()),
                    "unique_pct": round(
                        str_series.nunique() / len(str_series) * 100, 2
                    ),
                    "empty_count": empty_count,
                    "empty_pct": round(empty_count / len(str_series) * 100, 2)
                    if len(str_series) > 0
                    else 0.0,
                    "min_length": int(str_series.str.len().min()),
                    "max_length": int(str_series.str.len().max()),
                    "avg_length": round(float(str_series.str.len().mean()), 2),
                    "top_values": {str(k): int(v) for k, v in top_values.items()},
                }
            )
        profile["status"] = "OK"

    return profile


def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    """Generate a full data quality profile for a DataFrame."""
    total_rows = len(df)
    total_cells = total_rows * len(df.columns)
    total_nulls = int(df.isna().sum().sum())

    column_profiles = {}
    for col in df.columns:
        column_profiles[col] = profile_column(df[col])

    return {
        "total_rows": total_rows,
        "total_columns": len(df.columns),
        "total_cells": total_cells,
        "total_nulls": total_nulls,
        "overall_null_pct": round(total_nulls / total_cells * 100, 2)
        if total_cells > 0
        else 0.0,
        "columns": column_profiles,
    }


# ── Tier 1: Raw Data Quality Checks ────────────────────────────────────────


def validate_sales_parquet(data_path: Path) -> dict:
    """Validate sales.parquet with full data profiling and quality checks."""
    sales_path = data_path / "sales.parquet"

    if not sales_path.exists():
        raise ValidationError(f"sales.parquet not found at {sales_path}")

    df = pd.read_parquet(sales_path)
    row_count = len(df)
    logger.info(f"sales.parquet: {row_count:,} rows, {len(df.columns)} columns")

    if row_count == 0:
        raise ValidationError("sales.parquet has 0 rows")

    # ── Full column profile ──
    data_profile = profile_dataframe(df)

    # ── Required columns ──
    required_cols = [
        "id",
        "property_id",
        "property_locality",
        "purchase_price",
        "contract_date",
        "latitude",
        "longitude",
    ]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValidationError(f"Missing required columns: {missing_cols}")
    logger.info(f"All {len(required_cols)} required columns present")

    # ── Uniqueness checks ──
    id_duplicates = int(df["id"].duplicated().sum())
    logger.info(f"Duplicate IDs: {id_duplicates:,}")

    # Check property_id + contract_date uniqueness (should be unique sales)
    if "property_id" in df.columns and "contract_date" in df.columns:
        combo_key = (
            df["property_id"].astype(str) + "_" + df["contract_date"].astype(str)
        )
        combo_duplicates = int(combo_key.duplicated().sum())
        logger.info(f"Duplicate property_id+contract_date combos: {combo_duplicates:,}")
    else:
        combo_duplicates = None

    # ── Null checks on critical columns ──
    null_ids = int(df["id"].isna().sum())
    if null_ids > 0:
        raise ValidationError(f"Found {null_ids} null IDs")

    null_property_ids = int(df["property_id"].isna().sum())
    null_prices = int(df["purchase_price"].isna().sum())
    null_dates = int(df["contract_date"].isna().sum())

    logger.info(f"Null property_id: {null_property_ids:,}")
    logger.info(f"Null purchase_price: {null_prices:,}")
    logger.info(f"Null contract_date: {null_dates:,}")

    # ── Geocoding coverage ──
    geocoded = df["latitude"].notna() & df["longitude"].notna()
    geocoded_count = int(geocoded.sum())
    geocoding_pct = geocoded_count / row_count if row_count > 0 else 0
    logger.info(
        f"Geocoding coverage: {geocoded_count:,}/{row_count:,} ({geocoding_pct:.1%})"
    )
    if geocoding_pct < MIN_GEOCODING_COVERAGE:
        logger.warning(
            f"Geocoding coverage {geocoding_pct:.1%} is below threshold {MIN_GEOCODING_COVERAGE:.1%}"
        )

    # ── Price quality ──
    prices = pd.to_numeric(df["purchase_price"], errors="coerce")
    non_positive = int((prices <= 0).sum())
    null_prices_coerced = int(prices.isna().sum())
    if non_positive > 0:
        logger.warning(f"{non_positive:,} rows with purchase_price <= 0")
    logger.info(f"Null/invalid prices: {null_prices_coerced:,}")

    # ── Date range ──
    dates = pd.to_datetime(df["contract_date"], errors="coerce")
    valid_dates = dates.dropna()
    min_year = None
    max_year = None
    if len(valid_dates) > 0:
        min_year = int(valid_dates.dt.year.min())
        max_year = int(valid_dates.dt.year.max())
        logger.info(f"Contract date range: {min_year} - {max_year}")
        if min_year < MIN_CONTRACT_YEAR:
            logger.warning(
                f"Found contract dates before {MIN_CONTRACT_YEAR} (min: {min_year})"
            )
        if max_year > MAX_CONTRACT_YEAR:
            raise ValidationError(
                f"Found contract dates after {MAX_CONTRACT_YEAR} (max: {max_year})"
            )
    else:
        raise ValidationError("No valid contract dates found")

    # ── Cross-column consistency ──
    # settlement_date should be >= contract_date when both present
    consistency_issues = 0
    if "settlement_date" in df.columns:
        settlements = pd.to_datetime(df["settlement_date"], errors="coerce")
        valid_pairs = dates.notna() & settlements.notna()
        if valid_pairs.sum() > 0:
            invalid_pairs = (settlements[valid_pairs] < dates[valid_pairs]).sum()
            consistency_issues = int(invalid_pairs)
            if consistency_issues > 0:
                logger.warning(
                    f"{consistency_issues:,} rows with settlement_date < contract_date"
                )

    # ── Enum/accepted values check ──
    accepted_values_issues = {}
    if "primary_purpose" in df.columns:
        purposes = df["primary_purpose"].dropna().unique()
        logger.info(f"Primary purpose values: {list(purposes)}")

    if "nature_of_property" in df.columns:
        natures = df["nature_of_property"].dropna().unique()
        logger.info(f"Nature of property values: {list(natures)}")

    return {
        "file": "sales.parquet",
        "row_count": row_count,
        "column_count": len(df.columns),
        "data_profile": data_profile,
        "checks": {
            "required_columns_present": len(missing_cols) == 0,
            "missing_columns": missing_cols,
            "null_ids": null_ids,
            "id_duplicates": id_duplicates,
            "combo_duplicates": combo_duplicates,
            "null_property_ids": null_property_ids,
            "null_prices": null_prices,
            "null_dates": null_dates,
            "geocoding_count": geocoded_count,
            "geocoding_pct": round(geocoding_pct, 4),
            "geocoding_passes": geocoding_pct >= MIN_GEOCODING_COVERAGE,
            "non_positive_prices": non_positive,
            "null_invalid_prices": null_prices_coerced,
            "min_year": min_year,
            "max_year": max_year,
            "settlement_before_contract": consistency_issues,
        },
        "thresholds": {
            "min_geocoding_coverage": MIN_GEOCODING_COVERAGE,
            "min_contract_year": MIN_CONTRACT_YEAR,
            "max_contract_year": MAX_CONTRACT_YEAR,
        },
    }


def validate_property_growth(data_path: Path) -> dict:
    """Validate property_growth.parquet with full profiling."""
    growth_path = data_path / "property_growth.parquet"

    if not growth_path.exists():
        raise ValidationError(f"property_growth.parquet not found at {growth_path}")

    df = pd.read_parquet(growth_path)
    row_count = len(df)
    logger.info(f"property_growth.parquet: {row_count:,} rows")

    if row_count == 0:
        raise ValidationError("property_growth.parquet has 0 rows")

    # ── Full column profile ──
    data_profile = profile_dataframe(df)

    # ── CAGR range check ──
    cagr_stats = None
    cagr_out_of_range = 0
    if "avg_cagr" in df.columns:
        cagr = pd.to_numeric(df["avg_cagr"], errors="coerce")
        cagr_out_of_range = int(((cagr < MIN_CAGR) | (cagr > MAX_CAGR)).sum())
        if cagr_out_of_range > 0:
            logger.warning(
                f"{cagr_out_of_range:,} CAGR values outside [{MIN_CAGR}, {MAX_CAGR}]"
            )
        valid_cagr = cagr.dropna()
        if len(valid_cagr) > 0:
            cagr_stats = {
                "min": round(float(valid_cagr.min()), 6),
                "max": round(float(valid_cagr.max()), 6),
                "mean": round(float(valid_cagr.mean()), 6),
                "median": round(float(valid_cagr.median()), 6),
                "std": round(float(valid_cagr.std()), 6)
                if len(valid_cagr) > 1
                else 0.0,
                "null_count": int(cagr.isna().sum()),
                "out_of_range_count": cagr_out_of_range,
            }
            logger.info(f"CAGR stats: {cagr_stats}")
    else:
        raise ValidationError("property_growth.parquet missing 'avg_cagr' column")

    # ── Check required columns ──
    growth_required = [
        "property_id",
        "suburb",
        "avg_cagr",
        "total_growth",
        "years_held",
    ]
    growth_missing = [c for c in growth_required if c not in df.columns]
    if growth_missing:
        raise ValidationError(f"Missing growth columns: {growth_missing}")

    # ── Uniqueness ──
    growth_dupes = (
        int(df["property_id"].duplicated().sum())
        if "property_id" in df.columns
        else None
    )

    return {
        "file": "property_growth.parquet",
        "row_count": row_count,
        "column_count": len(df.columns),
        "data_profile": data_profile,
        "checks": {
            "required_columns_present": len(growth_missing) == 0,
            "missing_columns": growth_missing,
            "cagr_stats": cagr_stats,
            "cagr_out_of_range": cagr_out_of_range,
            "cagr_passes": cagr_out_of_range == 0,
            "property_id_duplicates": growth_dupes,
        },
        "thresholds": {
            "min_cagr": MIN_CAGR,
            "max_cagr": MAX_CAGR,
        },
    }


def validate_summary_files(data_path: Path) -> dict:
    """Validate street_summary.parquet and suburb_summary.parquet."""
    results = {}

    for filename in ["street_summary.parquet", "suburb_summary.parquet"]:
        filepath = data_path / filename
        if not filepath.exists():
            raise ValidationError(f"{filename} not found at {filepath}")

        df = pd.read_parquet(filepath)
        row_count = len(df)
        logger.info(f"{filename}: {row_count:,} rows")

        if row_count == 0:
            raise ValidationError(f"{filename} has 0 rows")

        # ── Full column profile ──
        data_profile = profile_dataframe(df)

        # ── Check for avg_cagr column ──
        has_cagr = "avg_cagr" in df.columns
        has_top_performer = "is_top_performer" in df.columns

        # ── Null checks on key columns ──
        key_cols = ["suburb", "unique_properties", "total_sales"]
        null_stats = {}
        for col in key_cols:
            if col in df.columns:
                null_stats[col] = int(df[col].isna().sum())

        results[filename] = {
            "row_count": row_count,
            "column_count": len(df.columns),
            "data_profile": data_profile,
            "checks": {
                "has_avg_cagr": has_cagr,
                "has_is_top_performer": has_top_performer,
                "null_stats": null_stats,
            },
        }

    return results


# ── Tier 2: Derived Data Quality & Reconciliation ──────────────────────────


def validate_h3_completeness(data_path: Path) -> dict:
    """Validate all H3 zoom levels (5-14) exist and have data."""
    h3_results = {}
    missing_zooms = []
    empty_zooms = []

    for resolution in range(5, 15):
        h3_path = data_path / f"h3_zoom_{resolution}.parquet"
        if not h3_path.exists():
            missing_zooms.append(resolution)
            h3_results[f"zoom_{resolution}"] = {"exists": False, "row_count": 0}
        else:
            df = pd.read_parquet(h3_path)
            row_count = len(df)
            if row_count == 0:
                empty_zooms.append(resolution)
            h3_results[f"zoom_{resolution}"] = {
                "exists": True,
                "row_count": row_count,
                "tile_count": int(df["h3_index"].nunique())
                if "h3_index" in df.columns
                else 0,
            }
            logger.info(f"H3 zoom {resolution}: {row_count:,} tiles")

    return {
        "zoom_levels": h3_results,
        "missing_zooms": missing_zooms,
        "empty_zooms": empty_zooms,
        "all_present": len(missing_zooms) == 0,
        "all_non_empty": len(empty_zooms) == 0,
    }


def validate_additional_files(data_path: Path) -> dict:
    """Validate optional pre-computed files exist and have data."""
    optional_files = [
        "suburb_year_stats.parquet",
        "street_year_stats.parquet",
        "property_history.parquet",
        "top_performers.parquet",
    ]
    results = {}

    for filename in optional_files:
        filepath = data_path / filename
        if not filepath.exists():
            results[filename] = {"exists": False, "row_count": 0}
            logger.warning(f"{filename} not found")
        else:
            df = pd.read_parquet(filepath)
            row_count = len(df)
            results[filename] = {
                "exists": True,
                "row_count": row_count,
                "column_count": len(df.columns),
                "data_profile": profile_dataframe(df),
            }
            logger.info(f"{filename}: {row_count:,} rows")

    return results


def validate_reconciliation(data_path: Path) -> dict:
    """
    Cross-file reconciliation checks.
    Verifies that derived aggregates are consistent with source data.
    """
    logger.info("\n--- Running reconciliation checks ---")
    results = {}

    # Load source data
    sales_df = pd.read_parquet(data_path / "sales.parquet")
    total_sales_rows = len(sales_df)
    logger.info(f"Source sales rows: {total_sales_rows:,}")

    # ── Check 1: Street summary total_sales reconciliation ──
    street_path = data_path / "street_summary.parquet"
    if street_path.exists():
        street_df = pd.read_parquet(street_path)
        street_total = int(street_df["total_sales"].sum())
        street_diff = abs(street_total - total_sales_rows)
        street_diff_pct = (
            round(street_diff / total_sales_rows * 100, 2)
            if total_sales_rows > 0
            else 0
        )

        results["street_sales_reconciliation"] = {
            "source_total": total_sales_rows,
            "street_sum": street_total,
            "difference": street_diff,
            "difference_pct": street_diff_pct,
            "passes": street_diff_pct <= RECONCILIATION_TOLERANCE * 100,
        }
        logger.info(
            f"Street reconciliation: source={total_sales_rows:,}, "
            f"street_sum={street_total:,}, diff={street_diff_pct}%"
        )
        if street_diff_pct > RECONCILIATION_TOLERANCE * 100:
            logger.warning(
                f"Street sales reconciliation failed: {street_diff_pct}% difference"
            )

    # ── Check 2: Suburb summary total_sales reconciliation ──
    suburb_path = data_path / "suburb_summary.parquet"
    if suburb_path.exists():
        suburb_df = pd.read_parquet(suburb_path)
        suburb_total = int(suburb_df["total_sales"].sum())
        suburb_diff = abs(suburb_total - total_sales_rows)
        suburb_diff_pct = (
            round(suburb_diff / total_sales_rows * 100, 2)
            if total_sales_rows > 0
            else 0
        )

        results["suburb_sales_reconciliation"] = {
            "source_total": total_sales_rows,
            "suburb_sum": suburb_total,
            "difference": suburb_diff,
            "difference_pct": suburb_diff_pct,
            "passes": suburb_diff_pct <= RECONCILIATION_TOLERANCE * 100,
        }
        logger.info(
            f"Suburb reconciliation: source={total_sales_rows:,}, "
            f"suburb_sum={suburb_total:,}, diff={suburb_diff_pct}%"
        )
        if suburb_diff_pct > RECONCILIATION_TOLERANCE * 100:
            logger.warning(
                f"Suburb sales reconciliation failed: {suburb_diff_pct}% difference"
            )

    # ── Check 3: Referential integrity — growth property_ids exist in sales ──
    growth_path = data_path / "property_growth.parquet"
    if growth_path.exists() and "property_id" in sales_df.columns:
        growth_df = pd.read_parquet(growth_path)
        if "property_id" in growth_df.columns:
            sales_ids = set(sales_df["property_id"].dropna().unique())
            growth_ids = set(growth_df["property_id"].dropna().unique())
            orphan_ids = growth_ids - sales_ids

            results["growth_referential_integrity"] = {
                "sales_unique_properties": len(sales_ids),
                "growth_unique_properties": len(growth_ids),
                "orphan_property_ids": len(orphan_ids),
                "passes": len(orphan_ids) == 0,
            }
            logger.info(
                f"Referential integrity: {len(growth_ids)} growth props, "
                f"{len(sales_ids)} sales props, {len(orphan_ids)} orphans"
            )
            if orphan_ids:
                logger.warning(f"Found {len(orphan_ids)} orphan property_ids in growth")

    # ── Check 4: Top performers validation ──
    top_path = data_path / "top_performers.parquet"
    if top_path.exists():
        top_df = pd.read_parquet(top_path)
        top_count = len(top_df)
        is_sorted = True
        if "avg_cagr" in top_df.columns and top_count > 1:
            is_sorted = bool(top_df["avg_cagr"].is_monotonic_decreasing)

        results["top_performers_validation"] = {
            "row_count": top_count,
            "expected_count": 100,
            "count_passes": top_count <= 100,
            "sorted_descending": is_sorted,
        }
        logger.info(f"Top performers: {top_count} rows, sorted desc: {is_sorted}")

    # ── Check 5: Property history consistency ──
    history_path = data_path / "property_history.parquet"
    if history_path.exists() and growth_path.exists():
        history_df = pd.read_parquet(history_path)
        growth_df = pd.read_parquet(growth_path)
        if "property_id" in history_df.columns and "property_id" in growth_df.columns:
            history_ids = set(history_df["property_id"].unique())
            growth_ids = set(growth_df["property_id"].unique())
            history_only = history_ids - growth_ids
            growth_only = growth_ids - history_ids

            results["history_growth_consistency"] = {
                "history_properties": len(history_ids),
                "growth_properties": len(growth_ids),
                "history_only": len(history_only),
                "growth_only": len(growth_only),
                "passes": len(history_only) == 0 and len(growth_only) == 0,
            }
            logger.info(
                f"History vs growth: {len(history_ids)} vs {len(growth_ids)}, "
                f"mismatches: {len(history_only) + len(growth_only)}"
            )

    # ── Check 6: H3 completeness ──
    results["h3_completeness"] = validate_h3_completeness(data_path)

    # ── Check 7: Additional files ──
    results["additional_files"] = validate_additional_files(data_path)

    return results


# ── Report Generation ──────────────────────────────────────────────────────


def generate_html_report(all_results: dict) -> str:
    """Generate an HTML report from validation results."""
    timestamp = all_results.get("timestamp", "Unknown")
    run_id = all_results.get("run_id", "Unknown")

    # Build summary table
    summary_rows = ""
    for check_name, check_data in all_results.get("checks_summary", {}).items():
        status = "PASS" if check_data.get("passes", True) else "FAIL"
        color = "#22c55e" if status == "PASS" else "#ef4444"
        summary_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{check_name}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb; text-align: center;">
                <span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">{status}</span>
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb; font-family: monospace; font-size: 12px;">
                {json.dumps(check_data.get("detail", {}), indent=2) if check_data.get("detail") else "-"}
            </td>
        </tr>"""

    # Build column null table for sales
    column_rows = ""
    sales_profile = all_results.get("sales", {}).get("data_profile", {})
    for col_name, col_data in sales_profile.get("columns", {}).items():
        null_pct = col_data.get("null_pct", 0)
        bar_color = (
            "#22c55e" if null_pct < 5 else "#f59e0b" if null_pct < 20 else "#ef4444"
        )
        column_rows += f"""
        <tr>
            <td style="padding: 6px; border-bottom: 1px solid #e5e7eb; font-family: monospace; font-size: 12px;">{col_name}</td>
            <td style="padding: 6px; border-bottom: 1px solid #e5e7eb; text-align: right;">{col_data.get("null_count", 0):,}</td>
            <td style="padding: 6px; border-bottom: 1px solid #e5e7eb; text-align: right;">{null_pct}%</td>
            <td style="padding: 6px; border-bottom: 1px solid #e5e7eb;">
                <div style="background: #e5e7eb; border-radius: 4px; height: 8px; width: 100px;">
                    <div style="background: {bar_color}; height: 100%; width: {100 - null_pct}%; border-radius: 4px;"></div>
                </div>
            </td>
            <td style="padding: 6px; border-bottom: 1px solid #e5e7eb; font-size: 12px;">{col_data.get("kind", "unknown")}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PropRoo Data Quality Report — {timestamp}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f9fafb; color: #111827; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: white; padding: 24px; border-radius: 8px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .header h1 {{ margin: 0 0 8px 0; font-size: 24px; }}
        .header p {{ margin: 0; color: #6b7280; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .card h2 {{ margin: 0 0 16px 0; font-size: 18px; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ text-align: left; padding: 8px; background: #f9fafb; font-weight: 600; font-size: 12px; text-transform: uppercase; color: #6b7280; border-bottom: 2px solid #e5e7eb; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }}
        .stat {{ background: #f9fafb; padding: 16px; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 28px; font-weight: 700; color: #111827; }}
        .stat-label {{ font-size: 12px; color: #6b7280; text-transform: uppercase; margin-top: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PropRoo Data Quality Report</h1>
            <p>Run ID: {run_id} | Generated: {timestamp}</p>
        </div>

        <div class="stats-grid">
            <div class="stat">
                <div class="stat-value">{all_results.get("sales", {}).get("row_count", 0):,}</div>
                <div class="stat-label">Total Sales Records</div>
            </div>
            <div class="stat">
                <div class="stat-value">{all_results.get("sales", {}).get("checks", {}).get("geocoding_pct", 0) * 100:.1f}%</div>
                <div class="stat-label">Geocoding Coverage</div>
            </div>
            <div class="stat">
                <div class="stat-value">{all_results.get("sales", {}).get("column_count", 0)}</div>
                <div class="stat-label">Columns</div>
            </div>
            <div class="stat">
                <div class="stat-value">{all_results.get("sales", {}).get("data_profile", {}).get("overall_null_pct", 0):.2f}%</div>
                <div class="stat-label">Overall Null Rate</div>
            </div>
        </div>

        <div class="card">
            <h2>Validation Checks Summary</h2>
            <table>
                <thead>
                    <tr>
                        <th>Check</th>
                        <th>Status</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
                    {summary_rows}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>Sales.parquet — Column Completeness</h2>
            <table>
                <thead>
                    <tr>
                        <th>Column</th>
                        <th>Null Count</th>
                        <th>Null %</th>
                        <th>Completeness</th>
                        <th>Type</th>
                    </tr>
                </thead>
                <tbody>
                    {column_rows}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>"""


# ── Main Orchestration ─────────────────────────────────────────────────────


def run_validation(data_dir: str, output_dir: str | None = None) -> dict:
    """Run all validations and produce structured report."""
    data_path = Path(data_dir)

    if not data_path.exists():
        raise ValidationError(f"Data directory not found: {data_path}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(f"Validating ETL output in {data_path}")
    logger.info("=" * 60)

    all_results = {
        "run_id": run_id,
        "timestamp": timestamp,
        "data_directory": str(data_path),
        "version": "2.0",
    }

    # ── Tier 1: Raw data quality ──
    logger.info("\n--- Tier 1: Validating sales.parquet ---")
    all_results["sales"] = validate_sales_parquet(data_path)

    logger.info("\n--- Tier 1: Validating property_growth.parquet ---")
    all_results["growth"] = validate_property_growth(data_path)

    logger.info("\n--- Tier 1: Validating summary files ---")
    all_results["summaries"] = validate_summary_files(data_path)

    # ── Tier 2: Derived data quality & reconciliation ──
    logger.info("\n--- Tier 2: Running reconciliation checks ---")
    all_results["reconciliation"] = validate_reconciliation(data_path)

    # ── Build checks summary for reporting ──
    checks_summary = {}

    # Sales checks
    sales_checks = all_results["sales"]["checks"]
    checks_summary["sales_required_columns"] = {
        "passes": sales_checks["required_columns_present"],
        "detail": {"missing": sales_checks["missing_columns"]},
    }
    checks_summary["sales_null_ids"] = {
        "passes": sales_checks["null_ids"] == 0,
        "detail": {"null_count": sales_checks["null_ids"]},
    }
    checks_summary["sales_id_uniqueness"] = {
        "passes": sales_checks["id_duplicates"] == 0,
        "detail": {"duplicates": sales_checks["id_duplicates"]},
    }
    checks_summary["sales_geocoding_coverage"] = {
        "passes": sales_checks["geocoding_passes"],
        "detail": {"coverage_pct": f"{sales_checks['geocoding_pct'] * 100:.1f}%"},
    }
    checks_summary["sales_date_range"] = {
        "passes": sales_checks["max_year"] <= MAX_CONTRACT_YEAR
        if sales_checks.get("max_year")
        else False,
        "detail": {
            "min_year": sales_checks["min_year"],
            "max_year": sales_checks["max_year"],
        },
    }

    # Growth checks
    growth_checks = all_results["growth"]["checks"]
    checks_summary["growth_cagr_range"] = {
        "passes": growth_checks["cagr_passes"],
        "detail": {"out_of_range": growth_checks["cagr_out_of_range"]},
    }

    # Reconciliation checks
    recon = all_results["reconciliation"]
    for key, val in recon.items():
        if isinstance(val, dict) and "passes" in val:
            checks_summary[f"recon_{key}"] = {
                "passes": val["passes"],
                "detail": {k: v for k, v in val.items() if k != "passes"},
            }

    all_results["checks_summary"] = checks_summary

    # ── Determine overall pass/fail ──
    all_pass = all(v.get("passes", True) for v in checks_summary.values())
    all_results["overall_status"] = "PASS" if all_pass else "FAIL"
    all_results["total_checks"] = len(checks_summary)
    all_results["passed_checks"] = sum(
        1 for v in checks_summary.values() if v.get("passes")
    )
    all_results["failed_checks"] = sum(
        1 for v in checks_summary.values() if not v.get("passes")
    )

    # ── Print summary ──
    logger.info("\n" + "=" * 60)
    logger.info("DATA QUALITY REPORT")
    logger.info("=" * 60)
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Overall Status: {all_results['overall_status']}")
    logger.info(
        f"Checks: {all_results['passed_checks']}/{all_results['total_checks']} passed"
    )

    sales = all_results["sales"]
    logger.info(
        f"\nSales: {sales['row_count']:,} rows, {sales['column_count']} columns"
    )
    logger.info(f"  Geocoding: {sales['checks']['geocoding_pct']:.1%}")
    logger.info(f"  Null IDs: {sales['checks']['null_ids']}")
    logger.info(f"  Duplicate IDs: {sales['checks']['id_duplicates']}")

    growth = all_results["growth"]
    cagr = growth["checks"].get("cagr_stats", {})
    if cagr:
        logger.info(f"\nGrowth: {growth['row_count']:,} rows")
        logger.info(
            f"  CAGR: {cagr.get('min')} to {cagr.get('max')} (mean: {cagr.get('mean')})"
        )

    logger.info(f"\nFailed checks: {all_results['failed_checks']}")
    for name, val in checks_summary.items():
        if not val.get("passes"):
            logger.warning(f"  FAIL: {name} — {val.get('detail', {})}")

    logger.info("=" * 60)

    # ── Write JSON report ──
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Remove data_profile from JSON for brevity (kept in HTML)
        json_report = {k: v for k, v in all_results.items()}

        report_json_path = output_path / "data-quality-report.json"
        with open(report_json_path, "w") as f:
            json.dump(json_report, f, indent=2, default=str)
        logger.info(f"\nJSON report written to {report_json_path}")

        # Write HTML report
        html_report = generate_html_report(all_results)
        report_html_path = output_path / "data-quality-report.html"
        with open(report_html_path, "w") as f:
            f.write(html_report)
        logger.info(f"HTML report written to {report_html_path}")

    if not all_pass:
        raise ValidationError(
            f"{all_results['failed_checks']} data quality check(s) failed. "
            f"See report for details."
        )

    logger.info("All data quality checks passed!")
    return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate ETL pipeline output with comprehensive data quality checks"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Path to the data directory containing parquet files",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Path to write JSON/HTML data quality reports",
    )
    args = parser.parse_args()

    try:
        run_validation(args.data_dir, output_dir=args.output_dir)
    except ValidationError as e:
        logger.error(f"VALIDATION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during validation: {e}")
        sys.exit(1)
