"""
PropRoo ETL Validation Script

Validates all output parquet files from the ETL pipeline before R2 upload.
Checks: row counts, schema integrity, geocoding coverage, CAGR range, date ranges.
Exits with code 1 if any critical validation fails.
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Validation thresholds
MIN_GEOCODING_COVERAGE = 0.80  # 80%
MIN_CAGR = -0.5  # -50%
MAX_CAGR = 2.0  # +200%
MIN_CONTRACT_YEAR = 2000
MAX_CONTRACT_YEAR = 2026


class ValidationError(Exception):
    """Raised when a critical validation check fails."""

    pass


def validate_sales_parquet(data_path: Path) -> dict:
    """Validate sales.parquet and return summary stats."""
    sales_path = data_path / "sales.parquet"

    if not sales_path.exists():
        raise ValidationError(f"sales.parquet not found at {sales_path}")

    df = pd.read_parquet(sales_path)
    row_count = len(df)
    logger.info(f"sales.parquet: {row_count:,} rows")

    if row_count == 0:
        raise ValidationError("sales.parquet has 0 rows")

    # Required columns
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

    # No null IDs
    null_ids = df["id"].isna().sum()
    if null_ids > 0:
        raise ValidationError(f"Found {null_ids} null IDs")
    logger.info("No null IDs")

    # Geocoding coverage
    geocoded = df["latitude"].notna() & df["longitude"].notna()
    geocoded_count = geocoded.sum()
    geocoding_pct = geocoded_count / row_count if row_count > 0 else 0
    logger.info(
        f"Geocoding coverage: {geocoded_count:,}/{row_count:,} ({geocoding_pct:.1%})"
    )
    if geocoding_pct < MIN_GEOCODING_COVERAGE:
        logger.warning(
            f"Geocoding coverage {geocoding_pct:.1%} is below threshold {MIN_GEOCODING_COVERAGE:.1%}"
        )

    # Price range sanity
    prices = pd.to_numeric(df["purchase_price"], errors="coerce")
    non_positive = (prices <= 0).sum()
    if non_positive > 0:
        logger.warning(f"{non_positive:,} rows with purchase_price <= 0")

    # Date range
    dates = pd.to_datetime(df["contract_date"], errors="coerce")
    valid_dates = dates.dropna()
    if len(valid_dates) > 0:
        min_year = valid_dates.dt.year.min()
        max_year = valid_dates.dt.year.max()
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

    return {
        "row_count": row_count,
        "geocoding_pct": geocoding_pct,
        "min_year": int(valid_dates.dt.year.min()) if len(valid_dates) > 0 else None,
        "max_year": int(valid_dates.dt.year.max()) if len(valid_dates) > 0 else None,
    }


def validate_property_growth(data_path: Path) -> dict:
    """Validate property_growth.parquet."""
    growth_path = data_path / "property_growth.parquet"

    if not growth_path.exists():
        raise ValidationError(f"property_growth.parquet not found at {growth_path}")

    df = pd.read_parquet(growth_path)
    row_count = len(df)
    logger.info(f"property_growth.parquet: {row_count:,} rows")

    if row_count == 0:
        raise ValidationError("property_growth.parquet has 0 rows")

    # CAGR range check
    if "avg_cagr" in df.columns:
        cagr = pd.to_numeric(df["avg_cagr"], errors="coerce")
        out_of_range = ((cagr < MIN_CAGR) | (cagr > MAX_CAGR)).sum()
        if out_of_range > 0:
            logger.warning(
                f"{out_of_range:,} CAGR values outside [{MIN_CAGR}, {MAX_CAGR}]"
            )
        cagr_stats = {
            "min": float(cagr.min()),
            "max": float(cagr.max()),
            "mean": float(cagr.mean()),
            "median": float(cagr.median()),
        }
        logger.info(f"CAGR stats: {cagr_stats}")
    else:
        raise ValidationError("property_growth.parquet missing 'avg_cagr' column")

    return {"row_count": row_count, "cagr_stats": cagr_stats}


def validate_summary_files(data_path: Path) -> dict:
    """Validate street_summary.parquet and suburb_summary.parquet exist and have data."""
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

        results[filename] = {"row_count": row_count}

    return results


def run_validation(data_dir: str) -> None:
    """Run all validations and print summary."""
    data_path = Path(data_dir)

    if not data_path.exists():
        raise ValidationError(f"Data directory not found: {data_path}")

    logger.info(f"Validating ETL output in {data_path}")
    logger.info("=" * 60)

    all_results = {}

    # 1. Validate sales.parquet
    logger.info("\n--- Validating sales.parquet ---")
    all_results["sales"] = validate_sales_parquet(data_path)

    # 2. Validate property_growth.parquet
    logger.info("\n--- Validating property_growth.parquet ---")
    all_results["growth"] = validate_property_growth(data_path)

    # 3. Validate summary files
    logger.info("\n--- Validating summary files ---")
    all_results["summaries"] = validate_summary_files(data_path)

    # Print final summary
    logger.info("\n" + "=" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 60)
    sales = all_results["sales"]
    logger.info(f"Total sales rows: {sales['row_count']:,}")
    logger.info(f"Geocoding coverage: {sales['geocoding_pct']:.1%}")
    logger.info(f"Year range: {sales['min_year']} - {sales['max_year']}")

    growth = all_results["growth"]
    cagr = growth.get("cagr_stats", {})
    logger.info(
        f"CAGR range: {cagr.get('min', 'N/A'):.4f} to {cagr.get('max', 'N/A'):.4f}"
    )
    logger.info(f"CAGR mean: {cagr.get('mean', 'N/A'):.4f}")
    logger.info(f"CAGR median: {cagr.get('median', 'N/A'):.4f}")

    summaries = all_results["summaries"]
    for fname, stats in summaries.items():
        logger.info(f"{fname}: {stats['row_count']:,} rows")

    logger.info("=" * 60)
    logger.info("All validations passed!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate ETL pipeline output")
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Path to the data directory containing parquet files",
    )
    args = parser.parse_args()

    try:
        run_validation(args.data_dir)
    except ValidationError as e:
        logger.error(f"VALIDATION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during validation: {e}")
        sys.exit(1)
