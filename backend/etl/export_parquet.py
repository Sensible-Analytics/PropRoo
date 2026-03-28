import io
import logging
import os
import tempfile
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import sqlalchemy
from app.config import settings
from app.database import get_r2_client

logger = logging.getLogger(__name__)

TABLES = ["sales", "property_growth", "street_summary", "suburb_summary"]


def export_all():
    if not settings.database_url:
        logger.warning("DATABASE_URL not set, skipping Parquet export")
        return
    r2 = get_r2_client()
    if not r2:
        logger.warning("R2 client not configured, skipping Parquet export")
        return
    engine = sqlalchemy.create_engine(settings.database_url)
    for table in TABLES:
        _export_table(engine, r2, table)


def _export_table(engine, r2_client, table: str):
    logger.info(f"Exporting {table} to Parquet...")
    tmp_files = []
    try:
        if table == "sales":
            # Chunk by 6-month date ranges on the indexed contract_date column
            # to avoid the Render free tier timeout on large sequential reads
            tmp_dir = tempfile.mkdtemp(prefix=f"parquet_export_{table}_")
            _export_sales_chunked(engine, r2_client, tmp_dir)
        else:
            _export_single_table(engine, r2_client, table)
    except Exception as e:
        logger.error(f"Failed to export table {table}: {e}")
        return


def _export_sales_chunked(engine, r2_client, tmp_dir: str):
    """Export sales table using date-range chunks to stay under timeout."""
    logger.info("Exporting sales via date-range chunks...")
    tmp_files = []
    with engine.connect() as conn:
        # Get min/max dates from indexed column for efficient range queries
        result = conn.execute(
            sqlalchemy.text(
                "SELECT MIN(contract_date)::text, MAX(contract_date)::text FROM sales"
            )
        )
        row = result.fetchone()
        min_date = row[0]
        max_date = row[1]

    if not min_date or not max_date:
        logger.warning("No date range found for sales table")
        return

    from datetime import datetime

    min_dt = datetime.strptime(str(min_date)[:10], "%Y-%m-%d")
    max_dt = datetime.strptime(str(max_date)[:10], "%Y-%m-%d")

    from dateutil.relativedelta import relativedelta

    chunk_start = min_dt
    chunk_num = 0
    while chunk_start <= max_dt:
        chunk_end = min(chunk_start + relativedelta(months=6), max_dt)
        where_clause = f"contract_date >= '{chunk_start.date()}' AND contract_date <= '{chunk_end.date()}'"
        tmp_file = os.path.join(tmp_dir, f"chunk_{chunk_num:03d}.parquet")

        try:
            df = pd.read_sql(
                f"SELECT * FROM sales WHERE {where_clause}",
                engine,
                parse_dates=["contract_date", "settlement_date"],
            )
            logger.info(
                f"  Chunk {chunk_num}: {len(df)} rows "
                f"({chunk_start.date()} to {chunk_end.date()})"
            )
            df.to_parquet(tmp_file, index=False, compression="snappy")
            tmp_files.append(tmp_file)
        except Exception as e:
            logger.error(
                f"  Chunk {chunk_num} failed ({chunk_start.date()} to {chunk_end.date()}): {e}"
            )

        chunk_start = chunk_end + relativedelta(days=1)
        chunk_num += 1

    if not tmp_files:
        logger.error("No sales chunks were exported")
        return

    # Merge all chunks into one parquet
    logger.info(f"Merging {len(tmp_files)} chunks...")
    dfs = [pd.read_parquet(f) for f in tmp_files]
    merged = pd.concat(dfs, ignore_index=True)
    logger.info(f"Merged {len(merged)} total sales rows")

    # Upload
    buffer = io.BytesIO()
    pq.write_table(
        pa.Table.from_pandas(merged),
        buffer,
        compression="snappy",
    )
    buffer.seek(0)
    _upload(r2_client, "sales", buffer.getvalue(), len(merged))

    # Cleanup tmp files
    for f in tmp_files:
        try:
            os.unlink(f)
        except Exception:
            pass
    try:
        os.rmdir(tmp_dir)
    except Exception:
        pass


def _export_single_table(engine, r2_client, table: str):
    """Export a non-sales table in one go (small tables)."""
    try:
        df = pd.read_sql(f"SELECT * FROM {table}", engine)
    except Exception as e:
        logger.error(f"Failed to read table {table}: {e}")
        return

    buffer = io.BytesIO()
    pq.write_table(
        pa.Table.from_pandas(df),
        buffer,
        compression="snappy",
    )
    buffer.seek(0)
    _upload(r2_client, table, buffer.getvalue(), len(df))


def _upload(r2_client, table: str, data: bytes, row_count: int):
    key = f"parquet/{table}/latest.parquet"
    try:
        r2_client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=data,
            ContentType="application/octet-stream",
        )
        logger.info(
            f"Exported {table}: {row_count} rows -> r2://{settings.r2_bucket_name}/{key}"
        )
    except Exception as e:
        logger.error(f"Failed to upload {table} to R2: {e}")
