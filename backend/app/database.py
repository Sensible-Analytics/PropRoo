import duckdb
import os

DATA_DIR = os.environ.get(
    "DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data")
)


def get_duck_conn():
    """Return a fresh in-memory DuckDB connection."""
    conn = duckdb.connect(database=":memory:")
    return conn


def parquet_path(filename: str) -> str:
    """Return absolute path to a parquet file."""
    return os.path.join(DATA_DIR, filename)


def query_parquet(sql: str, filename: str) -> list[dict]:
    """Read a parquet file and execute SQL against it, returning list of dicts."""
    conn = get_duck_conn()
    path = parquet_path(filename)
    # Register the parquet file as a view so the SQL can reference it by name
    conn.execute(f"CREATE VIEW data AS SELECT * FROM read_parquet('{path}')")
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    conn.close()
    return [dict(zip(columns, row)) for row in rows]
