print("[MAIN] Importing main module...")
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from .routers import sales, stats, map as map_router
from .database import Base, engine, SessionLocal
from .models import Sale
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("[MAIN] Creating FastAPI app...")
app = FastAPI(title="NSW Property Sales Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sales.router, prefix="/api/sales", tags=["sales"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(map_router.router, prefix="/api/map", tags=["map"])


@app.on_event("startup")
async def startup_event():
    try:
        Base.metadata.create_all(bind=engine)
        print("[STARTUP] Database tables created/verified")
    except Exception as e:
        print(f"[STARTUP] Error initializing database: {e}")


@app.get("/health")
def health_check():
    db = SessionLocal()
    try:
        count = db.query(Sale).count()
        return {"status": "ok", "record_count": count}
    except Exception as e:
        return {"status": "ok", "record_count": 0}
    finally:
        db.close()


@app.get("/api/health")
async def api_health_check():
    from app.database import get_pg_conn, release_pg_conn

    count = 0
    try:
        conn = get_pg_conn()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sales")
            count = cur.fetchone()[0]
            cur.close()
            release_pg_conn(conn)
    except Exception:
        pass
    return {"status": "ok", "record_count": count}


def run_ingestion(start_year: int, end_year: int):
    import subprocess

    try:
        result = subprocess.run(
            [
                "python",
                "ingest_2024.py",
                "--start-year",
                str(start_year),
                "--end-year",
                str(end_year),
            ],
            capture_output=True,
            text=True,
            timeout=1800,
            cwd="/app",
        )
        logger.info(f"Ingestion completed: {result.returncode}")
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")


def run_analytics():
    try:
        from app.analytics import calculate_growth_metrics

        calculate_growth_metrics()
        logger.info("Analytics completed")
    except Exception as e:
        logger.error(f"Analytics failed: {e}")


@app.post("/admin/ingest")
def trigger_ingestion(
    start_year: int = 2022,
    end_year: int = 2026,
    background_tasks: BackgroundTasks = None,
):
    background_tasks.add_task(run_ingestion, start_year, end_year)
    return {
        "status": "started",
        "message": f"Ingestion started for years {start_year}-{end_year}",
    }


@app.post("/admin/ingest-and-analyze")
def trigger_ingestion_with_analytics(
    start_year: int = 2022,
    end_year: int = 2026,
    background_tasks: BackgroundTasks = None,
):
    background_tasks.add_task(run_ingestion, start_year, end_year)
    background_tasks.add_task(run_analytics)
    return {
        "status": "started",
        "message": f"Ingestion and analytics started for years {start_year}-{end_year}",
    }


@app.post("/admin/analyze")
def trigger_analytics(background_tasks: BackgroundTasks = None):
    background_tasks.add_task(run_analytics)
    return {"status": "started", "message": "Analytics calculation started"}


def run_export():
    try:
        from etl.export_parquet import export_all

        export_all()
        logger.info("Parquet export completed")
    except Exception as e:
        logger.error(f"Export failed: {e}")


@app.post("/admin/export-parquet")
def trigger_export(background_tasks: BackgroundTasks = None):
    background_tasks.add_task(run_export)
    return {"status": "started", "message": "Parquet export to R2 started"}


@app.get("/admin/db-stats")
def get_db_stats():
    db = SessionLocal()
    try:
        return {
            "sales_count": db.query(Sale).count(),
            "years_available": db.query(Sale.contract_date)
            .filter(Sale.contract_date.isnot(None))
            .distinct()
            .count(),
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@app.get("/admin/debug")
def debug_info():
    db_url = os.environ.get("DATABASE_URL", "NOT SET")
    return {
        "database_url_set": db_url != "NOT SET",
        "database_url_prefix": db_url[:30] if db_url != "NOT SET" else "NOT SET",
        "data_dir": os.environ.get("DATA_DIR", "NOT SET"),
    }
