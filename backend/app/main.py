print("[MAIN] Importing main module...")
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from .routers import sales
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

app.include_router(sales.router, prefix="/api", tags=["sales"])


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
