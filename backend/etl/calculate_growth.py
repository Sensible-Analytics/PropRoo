import logging
import sys
from pathlib import Path

import duckdb
import h3
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.analytics import calculate_cagr

logger = logging.getLogger(__name__)


def run_all(data_dir: str | None = None) -> None:
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

    _calc_h3_tiles(sales_df, data_path)
    _calc_suburb_year_stats(sales_df, data_path)
    _calc_street_year_stats(sales_df, data_path)
    _calc_property_history(sales_df, data_path)
    _calc_top_performers(sales_df, data_path)

    logger.info("Growth calculation complete.")


def _calc_property_growth(sales_df: pd.DataFrame, data_path: Path) -> None:
    logger.info("Calculating property growth...")

    con = duckdb.connect()
    con.register("sales", sales_df)

    query = """
    WITH cleaned AS (
        SELECT
            property_id,
            property_locality,
            property_street_name,
            property_post_code,
            CAST(purchase_price AS DOUBLE) AS purchase_price,
            CAST(contract_date AS TIMESTAMP) AS contract_date,
            latitude,
            longitude
        FROM sales
        WHERE purchase_price IS NOT NULL
          AND contract_date IS NOT NULL
          AND CAST(purchase_price AS DOUBLE) > 0
    ),
    ranked AS (
        SELECT
            property_id,
            property_locality,
            property_street_name,
            property_post_code,
            purchase_price,
            contract_date,
            ROW_NUMBER() OVER (PARTITION BY property_id ORDER BY contract_date) AS rn_first,
            ROW_NUMBER() OVER (PARTITION BY property_id ORDER BY contract_date DESC) AS rn_last,
            FIRST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_price,
            LAST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_price,
            FIRST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_date,
            LAST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_date
        FROM cleaned
    ),
    property_metrics AS (
        SELECT DISTINCT
            property_id,
            property_locality AS suburb,
            property_street_name AS street_name,
            COALESCE(CAST(property_post_code AS INTEGER), 0) AS post_code,
            CAST(EXTRACT(YEAR FROM last_date) AS INTEGER) AS year,
            first_price,
            last_price,
            first_date,
            last_date,
            DATEDIFF('day', first_date, last_date) AS days_held
        FROM ranked
        WHERE rn_first = 1
    )
    SELECT
        property_id,
        suburb,
        street_name,
        post_code,
        year,
        first_price AS first_sale_price,
        last_price AS last_sale_price,
        CAST(EXTRACT(YEAR FROM first_date) AS INTEGER) AS first_sale_year,
        CAST(EXTRACT(YEAR FROM last_date) AS INTEGER) AS last_sale_year,
        days_held,
        CASE
            WHEN days_held > 0 THEN POW(last_price / first_price, 365.25 / days_held) - 1
            ELSE 0.0
        END AS cagr,
        CASE
            WHEN first_price > 0 THEN (last_price - first_price) / first_price
            ELSE 0.0
        END AS total_growth
    FROM property_metrics
    WHERE days_held > 0
    """

    result = con.execute(query).fetchdf()
    con.close()

    if result.empty:
        logger.warning("No property growth records to write")
        return

    result.loc[result["days_held"] < 182.625, "cagr"] = 0.0
    result["years_held"] = result["days_held"].apply(lambda d: int(max(0, d / 365.25)))
    result["avg_cagr"] = result["cagr"].round(6)
    result["total_growth"] = result["total_growth"].round(6)

    growth_df = result[
        [
            "property_id",
            "suburb",
            "street_name",
            "post_code",
            "year",
            "avg_cagr",
            "total_growth",
            "years_held",
            "first_sale_price",
            "last_sale_price",
            "first_sale_year",
            "last_sale_year",
        ]
    ]

    output_path = data_path / "property_growth.parquet"
    growth_df.to_parquet(output_path, index=False, engine="pyarrow")
    logger.info(f"Property growth: {len(growth_df)} records written to {output_path}")


def _calc_street_summary(sales_df: pd.DataFrame, data_path: Path) -> None:
    logger.info("Calculating street summary...")

    con = duckdb.connect()
    con.register("sales", sales_df)

    cagr_query = """
    WITH cleaned AS (
        SELECT
            property_id,
            property_locality,
            property_street_name,
            property_post_code,
            CAST(purchase_price AS DOUBLE) AS purchase_price,
            CAST(contract_date AS TIMESTAMP) AS contract_date
        FROM sales
        WHERE purchase_price IS NOT NULL
          AND contract_date IS NOT NULL
          AND CAST(purchase_price AS DOUBLE) > 0
    ),
    ranked AS (
        SELECT
            property_id,
            property_locality,
            property_street_name,
            property_post_code,
            purchase_price,
            contract_date,
            ROW_NUMBER() OVER (PARTITION BY property_id ORDER BY contract_date) AS rn_first,
            FIRST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_price,
            LAST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_price,
            FIRST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_date,
            LAST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_date
        FROM cleaned
    ),
    property_metrics AS (
        SELECT DISTINCT
            property_id,
            property_street_name,
            property_locality,
            property_post_code,
            first_price,
            last_price,
            DATEDIFF('day', first_date, last_date) AS days_held
        FROM ranked
        WHERE rn_first = 1 AND DATEDIFF('day', first_date, last_date) > 0
    )
    SELECT
        property_street_name AS street_name,
        property_locality AS suburb,
        COALESCE(CAST(property_post_code AS INTEGER), 0) AS post_code,
        property_id,
        CASE
            WHEN days_held >= 182 THEN
                CASE
                    WHEN first_price > 0 THEN POW(last_price / first_price, 365.25 / days_held) - 1
                    ELSE 0.0
                END
            ELSE 0.0
        END AS cagr
    FROM property_metrics
    """

    cagr_df = con.execute(cagr_query).fetchdf()

    street_query = """
    SELECT
        property_street_name AS street_name,
        property_locality AS suburb,
        COALESCE(CAST(property_post_code AS INTEGER), 0) AS post_code,
        COUNT(DISTINCT property_id) AS unique_properties,
        COUNT(property_id) AS total_sales,
        AVG(latitude) AS latitude,
        AVG(longitude) AS longitude
    FROM sales
    GROUP BY property_street_name, property_locality, property_post_code
    """

    street_stats = con.execute(street_query).fetchdf()
    con.close()

    if not cagr_df.empty:
        street_cagr = (
            cagr_df.groupby(["street_name", "suburb", "post_code"])
            .agg(
                avg_cagr=("cagr", "mean"),
                property_count=("cagr", "count"),
            )
            .reset_index()
        )
        street_stats = street_stats.merge(
            street_cagr,
            on=["street_name", "suburb", "post_code"],
            how="left",
        )
    else:
        street_stats["avg_cagr"] = 0.0
        street_stats["property_count"] = 0

    street_stats["avg_cagr"] = street_stats["avg_cagr"].fillna(0.0)
    street_stats["property_count"] = (
        street_stats["property_count"].fillna(0).astype(int)
    )

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

    con = duckdb.connect()
    con.register("sales", sales_df)

    cagr_query = """
    WITH cleaned AS (
        SELECT
            property_id,
            property_locality,
            CAST(purchase_price AS DOUBLE) AS purchase_price,
            CAST(contract_date AS TIMESTAMP) AS contract_date
        FROM sales
        WHERE purchase_price IS NOT NULL
          AND contract_date IS NOT NULL
          AND CAST(purchase_price AS DOUBLE) > 0
    ),
    ranked AS (
        SELECT
            property_id,
            property_locality,
            purchase_price,
            contract_date,
            ROW_NUMBER() OVER (PARTITION BY property_id ORDER BY contract_date) AS rn_first,
            FIRST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_price,
            LAST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_price,
            FIRST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_date,
            LAST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_date
        FROM cleaned
    ),
    property_metrics AS (
        SELECT DISTINCT
            property_id,
            property_locality,
            first_price,
            last_price,
            DATEDIFF('day', first_date, last_date) AS days_held
        FROM ranked
        WHERE rn_first = 1 AND DATEDIFF('day', first_date, last_date) > 0
    )
    SELECT
        property_locality AS suburb,
        property_id,
        CASE
            WHEN days_held >= 182 THEN
                CASE
                    WHEN first_price > 0 THEN POW(last_price / first_price, 365.25 / days_held) - 1
                    ELSE 0.0
                END
            ELSE 0.0
        END AS cagr
    FROM property_metrics
    """

    cagr_df = con.execute(cagr_query).fetchdf()

    suburb_query = """
    SELECT
        property_locality AS suburb,
        COUNT(DISTINCT property_id) AS unique_properties,
        COUNT(property_id) AS total_sales,
        AVG(latitude) AS latitude,
        AVG(longitude) AS longitude
    FROM sales
    GROUP BY property_locality
    """

    suburb_stats = con.execute(suburb_query).fetchdf()
    con.close()

    if not cagr_df.empty:
        suburb_cagr = (
            cagr_df.groupby(["suburb"]).agg(avg_cagr=("cagr", "mean")).reset_index()
        )
        suburb_stats = suburb_stats.merge(
            suburb_cagr,
            on=["suburb"],
            how="left",
        )
    else:
        suburb_stats["avg_cagr"] = 0.0

    suburb_stats["avg_cagr"] = suburb_stats["avg_cagr"].fillna(0.0)

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


def _calc_h3_tiles(sales_df: pd.DataFrame, data_path: Path) -> None:
    logger.info("Pre-computing H3 tiles for zoom levels 5-14...")

    con = duckdb.connect()
    con.register("sales", sales_df)

    cagr_query = """
    WITH cleaned AS (
        SELECT
            property_id,
            CAST(purchase_price AS DOUBLE) AS purchase_price,
            CAST(contract_date AS TIMESTAMP) AS contract_date,
            latitude,
            longitude
        FROM sales
        WHERE purchase_price IS NOT NULL
          AND contract_date IS NOT NULL
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND CAST(purchase_price AS DOUBLE) > 0
    ),
    ranked AS (
        SELECT
            property_id,
            purchase_price,
            contract_date,
            latitude,
            longitude,
            ROW_NUMBER() OVER (PARTITION BY property_id ORDER BY contract_date) AS rn_first,
            FIRST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_price,
            LAST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_price,
            FIRST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_date,
            LAST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_date
        FROM cleaned
    ),
    property_metrics AS (
        SELECT DISTINCT
            property_id,
            first_price,
            last_price,
            DATEDIFF('day', first_date, last_date) AS days_held
        FROM ranked
        WHERE rn_first = 1 AND DATEDIFF('day', first_date, last_date) > 0
    )
    SELECT
        property_id,
        CASE
            WHEN days_held >= 182 THEN
                CASE
                    WHEN first_price > 0 THEN POW(last_price / first_price, 365.25 / days_held) - 1
                    ELSE 0.0
                END
            ELSE 0.0
        END AS cagr
    FROM property_metrics
    """

    cagr_df = con.execute(cagr_query).fetchdf()
    cagr_map = dict(zip(cagr_df["property_id"], cagr_df["cagr"]))
    con.close()

    df = sales_df.copy()
    df["contract_date"] = pd.to_datetime(df["contract_date"], errors="coerce")
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude", "purchase_price"])
    df = df[df["purchase_price"] > 0]
    df["h3_cagr"] = df["property_id"].map(cagr_map)

    for resolution in range(5, 15):
        df["h3_index"] = df.apply(
            lambda row: h3.latlng_to_cell(
                float(row["latitude"]), float(row["longitude"]), resolution
            ),
            axis=1,
        )

        h3_stats = (
            df.groupby("h3_index")
            .agg(
                median_price=("purchase_price", "median"),
                avg_cagr=("h3_cagr", "mean"),
                sale_count=("property_id", "count"),
                centroid_lat=("latitude", "mean"),
                centroid_lng=("longitude", "mean"),
            )
            .reset_index()
        )

        h3_stats["avg_cagr"] = h3_stats["avg_cagr"].fillna(0.0)

        output_path = data_path / f"h3_zoom_{resolution}.parquet"
        h3_stats.to_parquet(output_path, index=False, engine="pyarrow")
        logger.info(
            f"H3 zoom {resolution}: {len(h3_stats)} tiles written to {output_path}"
        )


def _calc_suburb_year_stats(sales_df: pd.DataFrame, data_path: Path) -> None:
    logger.info("Pre-computing suburb year stats...")

    con = duckdb.connect()
    con.register("sales", sales_df)

    cagr_query = """
    WITH cleaned AS (
        SELECT
            property_id,
            CAST(purchase_price AS DOUBLE) AS purchase_price,
            CAST(contract_date AS TIMESTAMP) AS contract_date
        FROM sales
        WHERE purchase_price IS NOT NULL
          AND contract_date IS NOT NULL
          AND CAST(purchase_price AS DOUBLE) > 0
    ),
    ranked AS (
        SELECT
            property_id,
            purchase_price,
            contract_date,
            ROW_NUMBER() OVER (PARTITION BY property_id ORDER BY contract_date) AS rn_first,
            FIRST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_price,
            LAST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_price,
            FIRST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_date,
            LAST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_date
        FROM cleaned
    ),
    property_metrics AS (
        SELECT DISTINCT
            property_id,
            first_price,
            last_price,
            DATEDIFF('day', first_date, last_date) AS days_held
        FROM ranked
        WHERE rn_first = 1 AND DATEDIFF('day', first_date, last_date) > 0
    )
    SELECT
        property_id,
        CASE
            WHEN days_held >= 182 THEN
                CASE
                    WHEN first_price > 0 THEN POW(last_price / first_price, 365.25 / days_held) - 1
                    ELSE 0.0
                END
            ELSE 0.0
        END AS cagr
    FROM property_metrics
    """

    cagr_df = con.execute(cagr_query).fetchdf()
    cagr_map = dict(zip(cagr_df["property_id"], cagr_df["cagr"]))
    con.close()

    df = sales_df.copy()
    df["contract_date"] = pd.to_datetime(df["contract_date"], errors="coerce")
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce")
    df = df.dropna(subset=["purchase_price", "contract_date"])
    df = df[df["purchase_price"] > 0]
    df["year"] = df["contract_date"].dt.year
    df["cagr"] = df["property_id"].map(cagr_map)

    suburb_year = (
        df.groupby(["property_locality", "year"])
        .agg(
            avg_price=("purchase_price", "mean"),
            median_price=("purchase_price", "median"),
            sale_count=("property_id", "count"),
            avg_cagr=("cagr", "mean"),
        )
        .reset_index()
    )

    suburb_year = suburb_year.rename(columns={"property_locality": "suburb"})
    suburb_year["avg_cagr"] = suburb_year["avg_cagr"].fillna(0.0)

    output_path = data_path / "suburb_year_stats.parquet"
    suburb_year.to_parquet(output_path, index=False, engine="pyarrow")
    logger.info(
        f"Suburb year stats: {len(suburb_year)} records written to {output_path}"
    )


def _calc_street_year_stats(sales_df: pd.DataFrame, data_path: Path) -> None:
    logger.info("Pre-computing street year stats...")

    con = duckdb.connect()
    con.register("sales", sales_df)

    cagr_query = """
    WITH cleaned AS (
        SELECT
            property_id,
            CAST(purchase_price AS DOUBLE) AS purchase_price,
            CAST(contract_date AS TIMESTAMP) AS contract_date
        FROM sales
        WHERE purchase_price IS NOT NULL
          AND contract_date IS NOT NULL
          AND CAST(purchase_price AS DOUBLE) > 0
    ),
    ranked AS (
        SELECT
            property_id,
            purchase_price,
            contract_date,
            ROW_NUMBER() OVER (PARTITION BY property_id ORDER BY contract_date) AS rn_first,
            FIRST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_price,
            LAST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_price,
            FIRST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_date,
            LAST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_date
        FROM cleaned
    ),
    property_metrics AS (
        SELECT DISTINCT
            property_id,
            first_price,
            last_price,
            DATEDIFF('day', first_date, last_date) AS days_held
        FROM ranked
        WHERE rn_first = 1 AND DATEDIFF('day', first_date, last_date) > 0
    )
    SELECT
        property_id,
        CASE
            WHEN days_held >= 182 THEN
                CASE
                    WHEN first_price > 0 THEN POW(last_price / first_price, 365.25 / days_held) - 1
                    ELSE 0.0
                END
            ELSE 0.0
        END AS cagr
    FROM property_metrics
    """

    cagr_df = con.execute(cagr_query).fetchdf()
    cagr_map = dict(zip(cagr_df["property_id"], cagr_df["cagr"]))
    con.close()

    df = sales_df.copy()
    df["contract_date"] = pd.to_datetime(df["contract_date"], errors="coerce")
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce")
    df = df.dropna(subset=["purchase_price", "contract_date"])
    df = df[df["purchase_price"] > 0]
    df["year"] = df["contract_date"].dt.year
    df["cagr"] = df["property_id"].map(cagr_map)

    street_year = (
        df.groupby(["property_street_name", "property_locality", "year"])
        .agg(
            avg_price=("purchase_price", "mean"),
            median_price=("purchase_price", "median"),
            sale_count=("property_id", "count"),
            avg_cagr=("cagr", "mean"),
        )
        .reset_index()
    )

    street_year = street_year.rename(
        columns={"property_street_name": "street_name", "property_locality": "suburb"}
    )
    street_year["avg_cagr"] = street_year["avg_cagr"].fillna(0.0)

    output_path = data_path / "street_year_stats.parquet"
    street_year.to_parquet(output_path, index=False, engine="pyarrow")
    logger.info(
        f"Street year stats: {len(street_year)} records written to {output_path}"
    )


def _calc_property_history(sales_df: pd.DataFrame, data_path: Path) -> None:
    logger.info("Pre-computing property history...")

    con = duckdb.connect()
    con.register("sales", sales_df)

    query = """
    WITH cleaned AS (
        SELECT
            property_id,
            property_locality,
            property_street_name,
            CAST(purchase_price AS DOUBLE) AS purchase_price,
            CAST(contract_date AS TIMESTAMP) AS contract_date
        FROM sales
        WHERE purchase_price IS NOT NULL
          AND contract_date IS NOT NULL
          AND CAST(purchase_price AS DOUBLE) > 0
    ),
    ranked AS (
        SELECT
            property_id,
            property_locality,
            property_street_name,
            purchase_price,
            contract_date,
            ROW_NUMBER() OVER (PARTITION BY property_id ORDER BY contract_date) AS rn_first,
            COUNT(*) OVER (PARTITION BY property_id) AS sale_count,
            FIRST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_price,
            LAST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_price,
            FIRST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_date,
            LAST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_date
        FROM cleaned
    ),
    property_metrics AS (
        SELECT DISTINCT
            property_id,
            property_locality AS suburb,
            property_street_name AS street_name,
            sale_count,
            first_price,
            last_price,
            first_date,
            last_date,
            DATEDIFF('day', first_date, last_date) AS days_held
        FROM ranked
        WHERE rn_first = 1
    )
    SELECT
        property_id,
        suburb,
        street_name,
        sale_count,
        first_date AS first_sale_date,
        first_price AS first_sale_price,
        last_date AS last_sale_date,
        last_price AS last_sale_price,
        days_held,
        CASE
            WHEN days_held > 0 THEN POW(last_price / first_price, 365.25 / days_held) - 1
            ELSE 0.0
        END AS cagr
    FROM property_metrics
    WHERE sale_count >= 2 AND days_held > 0
    """

    result = con.execute(query).fetchdf()
    con.close()

    if result.empty:
        logger.warning("No property history records to write")
        return

    result.loc[result["days_held"] < 182.625, "cagr"] = 0.0
    result["avg_cagr"] = result["cagr"].round(6)

    history_df = result[
        [
            "property_id",
            "suburb",
            "street_name",
            "sale_count",
            "first_sale_date",
            "first_sale_price",
            "last_sale_date",
            "last_sale_price",
            "avg_cagr",
        ]
    ]

    output_path = data_path / "property_history.parquet"
    history_df.to_parquet(output_path, index=False, engine="pyarrow")
    logger.info(f"Property history: {len(history_df)} records written to {output_path}")


def _calc_top_performers(sales_df: pd.DataFrame, data_path: Path) -> None:
    logger.info("Pre-computing top performers...")

    con = duckdb.connect()
    con.register("sales", sales_df)

    query = """
    WITH cleaned AS (
        SELECT
            property_id,
            property_locality,
            property_street_name,
            CAST(purchase_price AS DOUBLE) AS purchase_price,
            CAST(contract_date AS TIMESTAMP) AS contract_date
        FROM sales
        WHERE purchase_price IS NOT NULL
          AND contract_date IS NOT NULL
          AND CAST(purchase_price AS DOUBLE) > 0
    ),
    ranked AS (
        SELECT
            property_id,
            property_locality,
            property_street_name,
            purchase_price,
            contract_date,
            ROW_NUMBER() OVER (PARTITION BY property_id ORDER BY contract_date) AS rn_first,
            FIRST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_price,
            LAST_VALUE(purchase_price) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_price,
            FIRST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date) AS first_date,
            LAST_VALUE(contract_date) OVER (PARTITION BY property_id ORDER BY contract_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_date
        FROM cleaned
    ),
    property_metrics AS (
        SELECT DISTINCT
            property_id,
            property_locality AS suburb,
            property_street_name AS street_name,
            first_price,
            last_price,
            first_date,
            last_date,
            DATEDIFF('day', first_date, last_date) AS days_held
        FROM ranked
        WHERE rn_first = 1
    )
    SELECT
        property_id,
        suburb,
        street_name,
        last_price AS last_sale_price,
        days_held,
        CASE
            WHEN days_held > 0 THEN POW(last_price / first_price, 365.25 / days_held) - 1
            ELSE 0.0
        END AS cagr
    FROM property_metrics
    WHERE days_held > 0
    """

    result = con.execute(query).fetchdf()
    con.close()

    if result.empty:
        logger.warning("No top performer records to write")
        return

    result.loc[result["days_held"] < 182.625, "cagr"] = 0.0
    result["years_held"] = result["days_held"].apply(lambda d: int(max(0, d / 365.25)))
    result["avg_cagr"] = result["cagr"].round(6)

    performers_df = result[
        [
            "property_id",
            "suburb",
            "street_name",
            "last_sale_price",
            "avg_cagr",
            "years_held",
        ]
    ]
    performers_df = performers_df.sort_values("avg_cagr", ascending=False).head(100)

    output_path = data_path / "top_performers.parquet"
    performers_df.to_parquet(output_path, index=False, engine="pyarrow")
    logger.info(
        f"Top performers: {len(performers_df)} records written to {output_path}"
    )


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
