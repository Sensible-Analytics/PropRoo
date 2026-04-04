print("[MAIN] Importing main module...")
from typing import Optional
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from .routers import sales, stats, map as map_router
from .database import get_duck_conn, parquet_path
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


@app.get("/health")
def health_check():
    path = parquet_path("sales.parquet")
    if path.startswith("s3://"):
        try:
            conn = get_duck_conn()
            result = conn.execute(
                f"SELECT COUNT(*) FROM read_parquet('{path}')"
            ).fetchone()
            conn.close()
            return {"status": "ok", "record_count": result[0]}
        except Exception:
            return {"status": "ok", "record_count": 0}
    if not os.path.exists(path):
        return {"status": "ok", "record_count": 0}
    try:
        conn = get_duck_conn()
        result = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()
        conn.close()
        return {"status": "ok", "record_count": result[0]}
    except Exception:
        return {"status": "ok", "record_count": 0}


@app.get("/api/health")
async def api_health_check():
    path = parquet_path("sales.parquet")
    if path.startswith("s3://"):
        try:
            conn = get_duck_conn()
            result = conn.execute(
                f"SELECT COUNT(*) FROM read_parquet('{path}')"
            ).fetchone()
            conn.close()
            return {"status": "ok", "record_count": result[0]}
        except Exception:
            return {"status": "ok", "record_count": 0}
    if not os.path.exists(path):
        return {"status": "ok", "record_count": 0}
    try:
        conn = get_duck_conn()
        result = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()
        conn.close()
        return {"status": "ok", "record_count": result[0]}
    except Exception:
        return {"status": "ok", "record_count": 0}


def run_ingestion(start_year: int, end_year: int):
    import subprocess

    try:
        result = subprocess.run(
            [
                "python",
                "etl/ingest.py",
                "--start-year",
                str(start_year),
                "--end-year",
                str(end_year),
            ],
            capture_output=True,
            text=True,
            timeout=1800,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        logger.info(f"Ingestion completed: {result.returncode}")
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")


def run_analytics():
    try:
        from etl.calculate_growth import run_all as run_growth_calculation
        from etl.ingest import DATA_DIR

        run_growth_calculation(data_dir=str(DATA_DIR))
        logger.info("Analytics completed")
    except Exception as e:
        logger.error(f"Analytics failed: {e}")


@app.post("/admin/ingest")
def trigger_ingestion(
    background_tasks: BackgroundTasks,
    start_year: int = 2022,
    end_year: int = 2026,
):
    background_tasks.add_task(run_ingestion, start_year, end_year)
    return {
        "status": "started",
        "message": f"Ingestion started for years {start_year}-{end_year}",
    }


@app.post("/admin/ingest-and-analyze")
def trigger_ingestion_with_analytics(
    background_tasks: BackgroundTasks,
    start_year: int = 2022,
    end_year: int = 2026,
):
    background_tasks.add_task(run_ingestion, start_year, end_year)
    background_tasks.add_task(run_analytics)
    return {
        "status": "started",
        "message": f"Ingestion and analytics started for years {start_year}-{end_year}",
    }


@app.post("/admin/analyze")
def trigger_analytics(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_analytics)
    return {"status": "started", "message": "Analytics calculation started"}


@app.get("/admin/db-stats")
def get_db_stats():
    path = parquet_path("sales.parquet")
    if not path.startswith("s3://") and not os.path.exists(path):
        return {"sales_count": 0, "years_available": 0}
    try:
        conn = get_duck_conn()
        count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[
            0
        ]
        years = conn.execute(
            f"SELECT COUNT(DISTINCT EXTRACT(YEAR FROM contract_date)) FROM read_parquet('{path}') WHERE contract_date IS NOT NULL"
        ).fetchone()[0]
        conn.close()
        return {"sales_count": count, "years_available": years}
    except Exception:
        logger.exception("Error fetching db stats")
        return {"error": "Failed to retrieve database statistics"}


@app.get("/admin/debug")
def debug_info():
    data_dir = os.environ.get(
        "DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data")
    )
    files = {
        "sales.parquet": os.path.exists(os.path.join(data_dir, "sales.parquet")),
        "property_growth.parquet": os.path.exists(
            os.path.join(data_dir, "property_growth.parquet")
        ),
        "street_summary.parquet": os.path.exists(
            os.path.join(data_dir, "street_summary.parquet")
        ),
        "suburb_summary.parquet": os.path.exists(
            os.path.join(data_dir, "suburb_summary.parquet")
        ),
    }
    return {
        "data_dir": data_dir,
        "files": files,
    }
