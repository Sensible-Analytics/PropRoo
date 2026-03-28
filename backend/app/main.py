print("[MAIN] Importing main module...")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import sales
from .database import Base, engine
import os
import subprocess

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
    return {"status": "ok"}


@app.post("/ingest")
def trigger_ingestion():
    """Trigger data ingestion (for admin use only)"""
    try:
        result = subprocess.run(
            ["python", "ingest_2024.py", "--start-year", "2020", "--end-year", "2024"],
            capture_output=True,
            text=True,
            timeout=600,
            cwd="/app",
        )
        return {
            "status": "completed" if result.returncode == 0 else "failed",
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "returncode": result.returncode,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
