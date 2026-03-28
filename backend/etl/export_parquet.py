import logging
import os
import sys

sys.path.insert(0, "/app")

logger = logging.getLogger(__name__)

TABLES = ["sales", "property_growth", "street_summary", "suburb_summary"]


def export_all():
    import duckdb
    from app.config import settings

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.warning("DATABASE_URL not set, skipping Parquet export")
        return

    if not settings.r2_access_key_id:
        logger.warning("R2 not configured, skipping Parquet export")
        return

    logger.info("Starting DuckDB postgres_scanner export...")
    conn = duckdb.connect(database=":memory:")
    conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
    conn.execute(f"CALL postgres_attach('{db_url}')")
    logger.info("PostgreSQL attached via postgres_scanner")

    r2_cfg = (
        f"S3_REGION 'auto', "
        f"S3_ACCESS_KEY_ID '{settings.r2_access_key_id}', "
        f"S3_SECRET_ACCESS_KEY '{settings.r2_secret_access_key}', "
        f"S3_ENDPOINT '{settings.r2_endpoint.replace('https://', '')}'"
    )

    for table in TABLES:
        logger.info(f"Exporting {table}...")
        try:
            conn.execute(f"""
                COPY (SELECT * FROM postgres.{table})
                TO 's3://{settings.r2_bucket_name}/parquet/{table}/latest.parquet'
                (FORMAT PARQUET, COMPRESSION 'snappy', {r2_cfg})
            """)
            logger.info(f"  {table} exported to R2")
        except Exception as e:
            logger.error(f"  {table} export failed: {e}")

    conn.close()
    logger.info("DuckDB export complete")
