import io
import logging
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
    try:
        CHUNK = 100_000 if table == "sales" else 500_000
        chunks = list(pd.read_sql(f"SELECT * FROM {table}", engine, chunksize=CHUNK))
        if len(chunks) == 1:
            df = chunks[0]
        else:
            df = pd.concat(chunks, ignore_index=True)
            logger.info(f"  Assembled {len(chunks)} chunks -> {len(df)} total rows")
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
    key = f"parquet/{table}/latest.parquet"
    try:
        r2_client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=buffer.getvalue(),
            ContentType="application/octet-stream",
        )
        logger.info(
            f"Exported {table}: {len(df)} rows -> r2://{settings.r2_bucket_name}/{key}"
        )
    except Exception as e:
        logger.error(f"Failed to upload {table} to R2: {e}")
