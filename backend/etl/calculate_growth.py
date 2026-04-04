import logging
import sys
from pathlib import Path

import pandas as pd

# Add backend to path so we can import calculate_cagr
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.analytics import calculate_cagr

logger = logging.getLogger(__name__)


def run_all(data_dir: str = None) -> None:
    if data_dir is None:
        data_dir = str(Path(__file__).resolve().parent.parent / "data")
    data_path = Path(data_dir)
    sales_path = data_path / "sales.parquet"

    if not sales_path.exists():
        raise FileNotFoundError(f"Sales parquet not found at {sales_path}")

    logger.info("Starting growth calculation from Parquet...")

    sales_df = pd.read_parquet(sales_path)
    logger.info(f"Loaded {len(sales_df)} sales records")

    _calc_property_growth(sales_df, data_path)
    _calc_street_summary(sales_df, data_path)
    _calc_suburb_summary(sales_df, data_path)

    logger.info("Growth calculation complete.")


def _calc_property_growth(sales_df: pd.DataFrame, data_path: Path) -> None:
    logger.info("Calculating property growth...")

    df = sales_df.copy()
    df["contract_date"] = pd.to_datetime(df["contract_date"], errors="coerce")
    df = df.dropna(subset=["purchase_price", "contract_date"])
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce")
    df = df[df["purchase_price"] > 0]
    df = df.sort_values(by=["property_id", "contract_date"])

    results = []
    for prop_id, group in df.groupby("property_id"):
        if len(group) < 2:
            continue
        first = group.iloc[0]
        last = group.iloc[-1]
        years = (last["contract_date"] - first["contract_date"]).days / 365.25
        cagr, total_growth = calculate_cagr(
            float(first["purchase_price"]),
            float(last["purchase_price"]),
            years,
        )
        results.append(
            {
                "property_id": prop_id,
                "suburb": last["property_locality"],
                "street_name": last["property_street_name"],
                "post_code": int(last["property_post_code"])
                if pd.notna(last["property_post_code"])
                else 0,
                "year": int(last["contract_date"].year),
                "avg_cagr": round(cagr, 6),
                "total_growth": round(total_growth, 6),
                "years_held": int(max(0, years)),
                "first_sale_price": float(first["purchase_price"]),
                "last_sale_price": float(last["purchase_price"]),
                "first_sale_year": int(first["contract_date"].year),
                "last_sale_year": int(last["contract_date"].year),
            }
        )

    if not results:
        logger.warning("No property growth records to write")
        return

    growth_df = pd.DataFrame(results)
    output_path = data_path / "property_growth.parquet"
    growth_df.to_parquet(output_path, index=False, engine="pyarrow")
    logger.info(f"Property growth: {len(results)} records written to {output_path}")


def _calc_street_summary(sales_df: pd.DataFrame, data_path: Path) -> None:
    logger.info("Calculating street summary...")

    df = sales_df.copy()
    df["contract_date"] = pd.to_datetime(df["contract_date"], errors="coerce")
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce")

    # Compute property-level CAGR for joining
    valid_df = df.dropna(subset=["purchase_price", "contract_date"])
    valid_df = valid_df[valid_df["purchase_price"] > 0]
    valid_df = valid_df.sort_values(by=["property_id", "contract_date"])

    cagr_results = []
    for prop_id, group in valid_df.groupby("property_id"):
        if len(group) < 2:
            continue
        first = group.iloc[0]
        last = group.iloc[-1]
        years = (last["contract_date"] - first["contract_date"]).days / 365.25
        cagr, _ = calculate_cagr(
            float(first["purchase_price"]),
            float(last["purchase_price"]),
            years,
        )
        cagr_results.append(
            {
                "property_id": prop_id,
                "avg_cagr": cagr,
            }
        )

    cagr_df = (
        pd.DataFrame(cagr_results)
        if cagr_results
        else pd.DataFrame(columns=["property_id", "avg_cagr"])
    )

    # Street-level aggregates from all sales
    street_stats = (
        df.groupby(["property_street_name", "property_locality", "property_post_code"])
        .agg(
            unique_properties=("property_id", "nunique"),
            total_sales=("property_id", "count"),
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
        )
        .reset_index()
    )

    street_stats = street_stats.rename(
        columns={
            "property_street_name": "street_name",
            "property_locality": "suburb",
            "property_post_code": "post_code",
        }
    )

    if not cagr_df.empty:
        street_cagr = (
            cagr_df.groupby(["property_id"])
            .agg(avg_cagr=("avg_cagr", "mean"))
            .reset_index()
        )
        # We need to map property_id back to street/suburb/postcode for aggregation
        # Instead, compute avg_cagr per street directly from cagr_results
        street_cagr_agg = []
        for prop_id, group in valid_df.groupby("property_id"):
            if len(group) < 2:
                continue
            first = group.iloc[0]
            last = group.iloc[-1]
            years = (last["contract_date"] - first["contract_date"]).days / 365.25
            cagr, _ = calculate_cagr(
                float(first["purchase_price"]),
                float(last["purchase_price"]),
                years,
            )
            street_cagr_agg.append(
                {
                    "street_name": last["property_street_name"],
                    "suburb": last["property_locality"],
                    "post_code": int(last["property_post_code"])
                    if pd.notna(last["property_post_code"])
                    else 0,
                    "avg_cagr": cagr,
                }
            )

        if street_cagr_agg:
            cagr_by_street = pd.DataFrame(street_cagr_agg)
            street_cagr_mean = (
                cagr_by_street.groupby(["street_name", "suburb", "post_code"])
                .agg(avg_cagr=("avg_cagr", "mean"))
                .reset_index()
            )
            street_stats = street_stats.merge(
                street_cagr_mean,
                on=["street_name", "suburb", "post_code"],
                how="left",
            )
        else:
            street_stats["avg_cagr"] = 0.0
    else:
        street_stats["avg_cagr"] = 0.0

    # property_count = number of properties with CAGR data
    if street_cagr_agg:
        cagr_by_street = pd.DataFrame(street_cagr_agg)
        property_count = (
            cagr_by_street.groupby(["street_name", "suburb", "post_code"])
            .agg(property_count=("avg_cagr", "count"))
            .reset_index()
        )
        street_stats = street_stats.merge(
            property_count,
            on=["street_name", "suburb", "post_code"],
            how="left",
        )
    else:
        street_stats["property_count"] = 0

    street_stats["avg_cagr"] = street_stats["avg_cagr"].fillna(0.0)

    # is_top_performer: 90th percentile threshold
    cagr_threshold = (
        street_stats["avg_cagr"].quantile(0.9)
        if not street_stats["avg_cagr"].dropna().empty
        else 0
    )
    street_stats["is_top_performer"] = (
        street_stats["avg_cagr"] >= cagr_threshold
    ).astype(int)

    output_path = data_path / "street_summary.parquet"
    street_stats.to_parquet(output_path, index=False, engine="pyarrow")
    logger.info(f"Street summary: {len(street_stats)} records written to {output_path}")


def _calc_suburb_summary(sales_df: pd.DataFrame, data_path: Path) -> None:
    logger.info("Calculating suburb summary...")

    df = sales_df.copy()
    df["contract_date"] = pd.to_datetime(df["contract_date"], errors="coerce")
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce")

    valid_df = df.dropna(subset=["purchase_price", "contract_date"])
    valid_df = valid_df[valid_df["purchase_price"] > 0]
    valid_df = valid_df.sort_values(by=["property_id", "contract_date"])

    # Suburb-level aggregates from all sales
    suburb_stats = (
        df.groupby(["property_locality"])
        .agg(
            unique_properties=("property_id", "nunique"),
            total_sales=("property_id", "count"),
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
        )
        .reset_index()
    )

    # Compute avg CAGR per suburb
    suburb_cagr_agg = []
    for prop_id, group in valid_df.groupby("property_id"):
        if len(group) < 2:
            continue
        first = group.iloc[0]
        last = group.iloc[-1]
        years = (last["contract_date"] - first["contract_date"]).days / 365.25
        cagr, _ = calculate_cagr(
            float(first["purchase_price"]),
            float(last["purchase_price"]),
            years,
        )
        suburb_cagr_agg.append(
            {
                "suburb": last["property_locality"],
                "avg_cagr": cagr,
            }
        )

    suburb_stats = suburb_stats.rename(
        columns={
            "property_locality": "suburb",
        }
    )

    if suburb_cagr_agg:
        cagr_by_suburb = pd.DataFrame(suburb_cagr_agg)
        suburb_cagr_mean = (
            cagr_by_suburb.groupby(["suburb"])
            .agg(avg_cagr=("avg_cagr", "mean"))
            .reset_index()
        )
        suburb_stats = suburb_stats.merge(
            suburb_cagr_mean,
            on=["suburb"],
            how="left",
        )
    else:
        suburb_stats["avg_cagr"] = 0.0

    suburb_stats["avg_cagr"] = suburb_stats["avg_cagr"].fillna(0.0)

    # is_top_performer: 90th percentile threshold
    cagr_threshold = (
        suburb_stats["avg_cagr"].quantile(0.9)
        if not suburb_stats["avg_cagr"].dropna().empty
        else 0
    )
    suburb_stats["is_top_performer"] = (
        suburb_stats["avg_cagr"] >= cagr_threshold
    ).astype(int)

    output_path = data_path / "suburb_summary.parquet"
    suburb_stats.to_parquet(output_path, index=False, engine="pyarrow")
    logger.info(f"Suburb summary: {len(suburb_stats)} records written to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    import argparse

    parser = argparse.ArgumentParser(
        description="Calculate growth metrics from Parquet"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Data directory (default: script's parent/data)",
    )
    args = parser.parse_args()
    run_all(data_dir=args.data_dir)
