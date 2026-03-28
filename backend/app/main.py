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
    import os
    import ssl
    import socket
    import subprocess

    DATABASE_URL = os.environ.get("DATABASE_URL", "")

    results = {"tests": []}

    try:
        from urllib.parse import urlparse

        parsed = urlparse(DATABASE_URL)
        hostname = parsed.hostname
        port = parsed.port or 5432

        results["tests"].append({"host": hostname, "port": port})

        try:
            proc = subprocess.run(
                ["psql", "--version"], capture_output=True, text=True, timeout=5
            )
            results["tests"].append({"psql": proc.stdout.strip()})
        except Exception as e:
            results["tests"].append({"psql_error": str(e)[:100]})

        try:
            result = subprocess.run(
                [
                    "psql",
                    f"postgresql://{parsed.username}:{parsed.password}@{hostname}:{port}{parsed.path}",
                    "-c",
                    "SELECT 1;",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "PGSSLMODE": "require"},
            )
            results["tests"].append(
                {"psql_require": result.stdout[:200] + result.stderr[:200]}
            )
        except Exception as e:
            results["tests"].append({"psql_require_error": str(e)[:200]})

        try:
            import psycopg2

            for mode in ["require"]:
                try:
                    conn = psycopg2.connect(
                        host=hostname,
                        port=port,
                        dbname=parsed.path[1:],
                        user=parsed.username,
                        password=parsed.password,
                        sslmode=mode,
                        sslcompression=0,
                    )
                    cur = conn.cursor()
                    cur.execute("SELECT 1;")
                    cur.close()
                    conn.close()
                    results["tests"].append({f"psycopg2_{mode}_nocomp": "success"})
                except Exception as e:
                    results["tests"].append({f"psycopg2_{mode}_nocomp": str(e)[:200]})
        except ImportError:
            results["tests"].append({"psycopg2": "not installed"})

    except Exception as e:
        results["error"] = str(e)

    return results
