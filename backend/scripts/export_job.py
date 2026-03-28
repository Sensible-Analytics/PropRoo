#!/usr/bin/env python3
"""Export sales to Parquet via DuckDB postgres_attach — pushes SQL to PostgreSQL."""

import logging
import os
import sys

sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("export")


def main():
    import duckdb
    from app.config import settings

    db_url = os.environ.get("DATABASE_URL")
    r2_bucket = settings.r2_bucket_name

    if not db_url:
        logger.error("DATABASE_URL not set")
        return

    logger.info("Connecting DuckDB + PostgreSQL via postgres_scanner...")
    conn = duckdb.connect(database=":memory:")
    conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
    conn.execute(f"CALL postgres_attach('{db_url}')")
    logger.info("PostgreSQL attached as 'postgres' schema")

    r2_cfg = (
        f"S3_REGION 'auto', "
        f"S3_ACCESS_KEY_ID '{settings.r2_access_key_id}', "
        f"S3_SECRET_ACCESS_KEY '{settings.r2_secret_access_key}', "
        f"S3_ENDPOINT '{settings.r2_endpoint.replace('https://', '')}'"
    )

    for table in ["sales", "property_growth", "street_summary", "suburb_summary"]:
        logger.info(f"Exporting {table}...")
        conn.execute(f"""
            COPY (SELECT * FROM postgres.{table})
            TO 's3://{r2_bucket}/parquet/{table}/latest.parquet'
            (FORMAT PARQUET, COMPRESSION 'snappy', {r2_cfg})
        """)
        logger.info(f"  {table} exported")

    logger.info("All exports complete!")
    conn.close()


if __name__ == "__main__":
    main()
