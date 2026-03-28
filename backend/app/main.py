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

        ip_url = f"postgresql://{parsed.username}:{parsed.password}@18.142.152.125:{parsed.port}{parsed.path}"
        results["tests"].append({"ip_url": ip_url})

        for ssl_mode in ["disable", "prefer", "require"]:
            try:
                conn = psycopg2.connect(ip_url, sslmode=ssl_mode)
                cur = conn.cursor()
                cur.execute("SELECT 1;")
                cur.close()
                conn.close()
                results["tests"].append({f"ip_{ssl_mode}": "success"})
            except Exception as e:
                results["tests"].append({f"ip_{ssl_mode}": str(e)[:100]})

    except Exception as e:
        results["error"] = str(e)

    return results
