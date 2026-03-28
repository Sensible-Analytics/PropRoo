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

    results = {"cert_check": {}, "tests": []}

    try:
        from urllib.parse import urlparse

        parsed = urlparse(DATABASE_URL)

        cert_paths = [
            "/opt/render/.postgresql/root.crt",
            "/etc/ssl/certs/ca-certificates.crt",
            "/etc/pki/tls/certs/ca-bundle.crt",
        ]

        for path in cert_paths:
            try:
                with open(path, "r") as f:
                    results["cert_check"][path] = "exists"
            except:
                results["cert_check"][path] = "not found"

        for ssl_mode in ["require", "verify-ca"]:
            try:
                conn = psycopg2.connect(DATABASE_URL, sslmode=ssl_mode)
                cur = conn.cursor()
                cur.execute("SELECT 1;")
                cur.close()
                conn.close()
                results["tests"].append({f"{ssl_mode}_system_cert": "success"})
            except Exception as e:
                results["tests"].append({f"{ssl_mode}_system_cert": str(e)[:200]})

    except Exception as e:
        results["error"] = str(e)

    return results
