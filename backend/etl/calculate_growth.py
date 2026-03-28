import logging
import pandas as pd
import psycopg2.extras
from app.config import settings
from app.analytics import calculate_cagr

logger = logging.getLogger(__name__)
CHUNK_SIZE = 50_000


def run_all():
    if not settings.database_url:
        logger.warning("DATABASE_URL not set, skipping growth calculation")
        return
    import psycopg2

    conn = psycopg2.connect(settings.database_url)
    try:
        _calc_property_growth(conn)
        _calc_street_summary(conn)
        _calc_suburb_summary(conn)
    finally:
        conn.close()


def _calc_property_growth(conn):
    logger.info("Calculating property growth...")
    import sqlalchemy

    engine_url = settings.database_url
    engine = sqlalchemy.create_engine(engine_url)

    results = []
    query = """
        SELECT property_id, property_street_name, property_locality, property_post_code,
               purchase_price, contract_date
        FROM sales
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY property_id, contract_date
    """

    df = pd.read_sql(query, engine)
    if df.empty:
        logger.warning("No sale data found for growth calculation")
        return

    df["contract_date"] = pd.to_datetime(df["contract_date"], errors="coerce")
    df = df.dropna(subset=["purchase_price", "contract_date"])
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce")
    df = df[df["purchase_price"] > 0]
    df = df.sort_values(by=["property_id", "contract_date"])

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
            (
                int(prop_id),
                last["property_locality"],
                last["property_street_name"],
                int(last["property_post_code"] or 0),
                last["contract_date"].year,
                round(cagr, 6),
                round(total_growth, 6),
                int(max(0, years)),
                float(first["purchase_price"]),
                float(last["purchase_price"]),
                first["contract_date"].year,
                last["contract_date"].year,
            )
        )

    if not results:
        logger.warning("No property growth records to insert")
        return

    staging = "property_growth_staging"
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"""
            CREATE TABLE {staging} (
                id SERIAL PRIMARY KEY,
                property_id INTEGER NOT NULL,
                suburb VARCHAR(50) NOT NULL,
                street_name VARCHAR(100) NOT NULL,
                post_code INTEGER NOT NULL,
                year INTEGER NOT NULL,
                avg_cagr DECIMAL(10,6),
                total_growth DECIMAL(10,6),
                years_held INTEGER NOT NULL,
                first_sale_price DECIMAL(15,2),
                last_sale_price DECIMAL(15,2),
                first_sale_year INTEGER,
                last_sale_year INTEGER,
                UNIQUE (property_id, year)
            )
        """)
        psycopg2.extras.execute_values(
            cur,
            f"""INSERT INTO {staging} (
                property_id, suburb, street_name, post_code, year,
                avg_cagr, total_growth, years_held,
                first_sale_price, last_sale_price, first_sale_year, last_sale_year
            ) VALUES %s""",
            results,
        )
        cur.execute("ALTER TABLE property_growth RENAME TO property_growth_old")
        cur.execute(f"ALTER TABLE {staging} RENAME TO property_growth")
        cur.execute("DROP TABLE property_growth_old")
        conn.commit()

    logger.info(f"Property growth: {len(results)} records written")


def _calc_street_summary(conn):
    logger.info("Calculating street summary...")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE street_summary RESTART IDENTITY")
        cur.execute("""
            INSERT INTO street_summary (street_name, suburb, post_code, unique_properties, total_sales, avg_cagr, property_count)
            SELECT
                s.property_street_name,
                s.property_locality,
                s.property_post_code,
                COUNT(DISTINCT s.property_id),
                COUNT(s.id),
                COALESCE(AVG(pg.avg_cagr), 0),
                COUNT(DISTINCT pg.property_id)
            FROM sales s
            LEFT JOIN property_growth pg ON pg.property_id = s.property_id
            GROUP BY s.property_street_name, s.property_locality, s.property_post_code
            ON CONFLICT (street_name, suburb, post_code) DO UPDATE
            SET avg_cagr = EXCLUDED.avg_cagr,
                total_sales = EXCLUDED.total_sales,
                unique_properties = EXCLUDED.unique_properties,
                property_count = EXCLUDED.property_count
        """)
        conn.commit()
    logger.info("Street summary updated")


def _calc_suburb_summary(conn):
    logger.info("Calculating suburb summary...")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE suburb_summary RESTART IDENTITY")
        cur.execute("""
            INSERT INTO suburb_summary (suburb, post_code, unique_properties, total_sales, avg_cagr, property_count)
            SELECT
                s.property_locality,
                s.property_post_code,
                COUNT(DISTINCT s.property_id),
                COUNT(s.id),
                COALESCE(AVG(pg.avg_cagr), 0),
                COUNT(DISTINCT pg.property_id)
            FROM sales s
            LEFT JOIN property_growth pg ON pg.property_id = s.property_id
            GROUP BY s.property_locality, s.property_post_code
            ON CONFLICT (suburb, post_code) DO UPDATE
            SET avg_cagr = EXCLUDED.avg_cagr,
                total_sales = EXCLUDED.total_sales,
                unique_properties = EXCLUDED.unique_properties,
                property_count = EXCLUDED.property_count
        """)
        conn.commit()
    logger.info("Suburb summary updated")
