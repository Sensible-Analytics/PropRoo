print("[MAIN] Importing main module...")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import sales
from .database import Base, engine
import os

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
    """Initialize database on startup"""
    try:
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        print("[STARTUP] Database tables created/verified")
    except Exception as e:
        print(f"[STARTUP] Error initializing database: {e}")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/test-db")
def test_db():
    """Test database connection"""
    import psycopg2
    import ssl
    import os

    DATABASE_URL = os.environ.get("DATABASE_URL", "")

    results = {"url_params": {}, "tests": []}

    try:
        from urllib.parse import urlparse

        parsed = urlparse(DATABASE_URL)
        results["url_params"] = {
            "scheme": parsed.scheme,
            "hostname": parsed.hostname,
            "port": parsed.port,
            "path": parsed.path,
        }
    except Exception as e:
        results["url_parsing_error"] = str(e)

    test_configs = [
        {"name": "default", "params": {}},
        {"name": "sslmode=disable", "params": {"sslmode": "disable"}},
        {"name": "sslmode=allow", "params": {"sslmode": "allow"}},
        {"name": "sslmode=prefer", "params": {"sslmode": "prefer"}},
        {"name": "sslmode=require", "params": {"sslmode": "require"}},
        {"name": "sslmode=verify-ca", "params": {"sslmode": "verify-ca"}},
        {"name": "sslmode=verify-full", "params": {"sslmode": "verify-full"}},
    ]

    for config in test_configs:
        try:
            conn = psycopg2.connect(DATABASE_URL, **config["params"])
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            cur.close()
            conn.close()
            results["tests"].append({config["name"]: "success"})
        except Exception as e:
            results["tests"].append({config["name"]: str(e)})

    return results
