#!/usr/bin/env python3
"""Standalone parquet export script — run as a Render one-off job."""

import io
import logging
import os
import sys

sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("export")


def main():
    from dateutil.relativedelta import relativedelta
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    import sqlalchemy
    from app.config import settings
    from app.database import get_r2_client
    from datetime import datetime

    db_url = settings.database_url
    r2 = get_r2_client()
    bucket = settings.r2_bucket_name

    if not db_url:
        logger.error("DATABASE_URL not set")
        return
    if not r2:
        logger.error("R2 not configured")
        return

    engine = sqlalchemy.create_engine(db_url)
    _export_sales(engine, r2, bucket)

    for table in ["property_growth", "street_summary", "suburb_summary"]:
        _export_small_table(engine, r2, bucket, table)

    logger.info("All exports complete!")


def _export_sales(engine, r2_client, bucket: str):
    logger.info("Exporting sales...")
    with engine.connect() as conn:
        result = conn.execute(
            sqlalchemy.text(
                "SELECT MIN(contract_date)::text, MAX(contract_date)::text FROM sales"
            )
        )
        row = result.fetchone()
        min_date = row[0]
        max_date = row[1]

    min_dt = datetime.strptime(str(min_date)[:10], "%Y-%m-%d")
    max_dt = datetime.strptime(str(max_date)[:10], "%Y-%m-%d")
    logger.info(f"Sales date range: {min_dt.date()} to {max_dt.date()}")

    chunk_start = min_dt
    chunk_num = 0
    all_dfs = []
    while chunk_start <= max_dt:
        chunk_end = min(chunk_start + relativedelta(months=6), max_dt)
        where = f"contract_date >= '{chunk_start.date()}' AND contract_date <= '{chunk_end.date()}'"
        try:
            df = pd.read_sql(
                f"SELECT * FROM sales WHERE {where}",
                engine,
                parse_dates=["contract_date", "settlement_date"],
            )
            logger.info(
                f"  Chunk {chunk_num}: {len(df)} rows "
                f"({chunk_start.date()} to {chunk_end.date()})"
            )
            all_dfs.append(df)
        except Exception as e:
            logger.error(f"  Chunk {chunk_num} failed: {e}")

        chunk_start = chunk_end + relativedelta(days=1)
        chunk_num += 1

    if not all_dfs:
        logger.error("No sales data exported")
        return

    merged = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"Merged {len(merged)} total sales rows")

    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pandas(merged), buf, compression="snappy")
    buf.seek(0)
    data = buf.getvalue()
    r2_client.put_object(
        Bucket=bucket,
        Key="parquet/sales/latest.parquet",
        Body=data,
        ContentType="application/octet-stream",
    )
    logger.info(
        f"Sales export: {len(merged)} rows -> r2://{bucket}/parquet/sales/latest.parquet "
        f"({len(data) / 1024 / 1024:.1f} MB)"
    )


def _export_small_table(engine, r2_client, bucket: str, table: str):
    try:
        df = pd.read_sql(f"SELECT * FROM {table}", engine)
    except Exception as e:
        logger.error(f"Failed to read {table}: {e}")
        return

    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pandas(df), buf, compression="snappy")
    buf.seek(0)
    data = buf.getvalue()
    r2_client.put_object(
        Bucket=bucket,
        Key=f"parquet/{table}/latest.parquet",
        Body=data,
        ContentType="application/octet-stream",
    )
    logger.info(
        f"Exported {table}: {len(df)} rows -> r2://{bucket}/parquet/{table}/latest.parquet"
    )


if __name__ == "__main__":
    main()
