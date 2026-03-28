from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os
import sys

DATABASE_URL = os.environ.get("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

if DATABASE_URL:
    if DATABASE_URL.startswith("postgresql://"):
        sys.stderr.write("[DB] Using PostgreSQL\n")
        from urllib.parse import urlparse

        engine = create_engine(
            DATABASE_URL,
            poolclass=NullPool,
            connect_args={
                "connect_timeout": 30,
                "sslmode": "require",
                "keepalives": 1,
                "keepalives_idle": 60,
            },
        )
    else:
        engine = create_engine(DATABASE_URL)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.environ.get("DATA_DIR", "/tmp")
    DB_PATH = os.path.join(DATA_DIR, "sales.db")
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    sys.stderr.write(f"[DB] Using SQLite at {DB_PATH}\n")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_pg_conn():
    if not DATABASE_URL or not DATABASE_URL.startswith("postgresql://"):
        return None
    import psycopg2

    return psycopg2.connect(DATABASE_URL)


def release_pg_conn(conn):
    if conn:
        conn.close()


def get_duck_conn():
    import duckdb

    conn = duckdb.connect(database=":memory:")
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    from app.config import settings

    if settings.r2_access_key_id and settings.r2_endpoint:
        conn.execute("SET s3_region='auto';")
        conn.execute(f"SET s3_access_key_id='{settings.r2_access_key_id}';")
        conn.execute(f"SET s3_secret_access_key='{settings.r2_secret_access_key}';")
        conn.execute(
            f"SET s3_endpoint='{settings.r2_endpoint.replace('https://', '')}';"
        )
        conn.execute("SET s3_url_style='path';")
    return conn


def get_r2_client():
    import boto3
    from app.config import settings

    if not settings.r2_access_key_id or not settings.r2_endpoint:
        return None
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )
