import duckdb
import os

DATA_DIR = os.environ.get(
    "DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data")
)

R2_BUCKET = os.environ.get("R2_BUCKET_NAME")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT")


def _configure_r2(conn):
    if R2_BUCKET and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_ENDPOINT_URL:
        conn.execute("INSTALL httpfs")
        conn.execute("LOAD httpfs")
        conn.execute(f"SET s3_region='auto'")
        conn.execute(f"SET s3_access_key_id='{R2_ACCESS_KEY_ID}'")
        conn.execute(f"SET s3_secret_access_key='{R2_SECRET_ACCESS_KEY}'")
        conn.execute(f"SET s3_endpoint='{R2_ENDPOINT_URL.replace('https://', '')}'")
        conn.execute(f"SET s3_url_style='path'")
        conn.execute(f"SET s3_use_ssl='true'")


def get_duck_conn():
    conn = duckdb.connect(database=":memory:")
    _configure_r2(conn)
    return conn


def parquet_path(filename: str) -> str:
    if R2_BUCKET and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_ENDPOINT_URL:
        return f"s3://{R2_BUCKET}/{filename}"
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
