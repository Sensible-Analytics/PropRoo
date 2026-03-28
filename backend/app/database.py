from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os
import sys
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")
sys.stderr.write(
    f"[DB DEBUG] DATABASE_URL: {DATABASE_URL[:80] if DATABASE_URL else 'None'}\n"
)
sys.stderr.write(f"[DB DEBUG] DATA_DIR: {os.environ.get('DATA_DIR', 'Not set')}\n")

RAILWAY_TEST_VARIABLE = "THIS_SHOULD_APPEAR_IN_LOGS_IF_CODE_IS_LOADED"

if DATABASE_URL:
    if DATABASE_URL.startswith("postgresql://"):
        sys.stderr.write(f"[DB DEBUG] Using PostgreSQL with NullPool\n")
        engine = create_engine(
            DATABASE_URL,
            poolclass=NullPool,
            connect_args={
                "connect_timeout": 10,
                "sslmode": "require",
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
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

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
