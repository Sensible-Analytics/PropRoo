import duckdb
import os
import boto3

DATA_DIR = os.environ.get("DATA_DIR", "/tmp")

R2_BUCKET = os.environ.get("R2_BUCKET_NAME")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT")

PARQUET_FILES = [
    "sales.parquet",
    "property_growth.parquet",
    "street_summary.parquet",
    "suburb_summary.parquet",
]


def download_parquet_from_r2():
    if not all([R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL]):
        return
    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )
    os.makedirs(DATA_DIR, exist_ok=True)
    for f in PARQUET_FILES:
        local = os.path.join(DATA_DIR, f)
        s3.download_file(R2_BUCKET, f, local)


def get_duck_conn():
    return duckdb.connect(database=":memory:")


def parquet_path(filename: str) -> str:
    return os.path.join(DATA_DIR, filename)


def query_parquet(sql: str, filename: str) -> list[dict]:
    conn = get_duck_conn()
    path = parquet_path(filename)
    conn.execute(f"CREATE VIEW data AS SELECT * FROM read_parquet('{path}')")
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    conn.close()
    return [dict(zip(columns, row)) for row in rows]
