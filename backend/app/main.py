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

    DATABASE_URL = os.environ.get("DATABASE_URL", "")

    results = {"tests": []}

    try:
        from urllib.parse import urlparse

        parsed = urlparse(DATABASE_URL)
        hostname = parsed.hostname
        port = parsed.port or 5432

        results["tests"].append({"host": hostname, "port": port})

        try:
            with socket.create_connection((hostname, port), timeout=10) as sock:
                sock.sendall(b"\x00\x03\x00\x00")
                data = sock.recv(1024)
                results["tests"].append({"raw_tcp": f"Received: {data[:50]}"})
        except Exception as e:
            results["tests"].append({"raw_tcp_error": str(e)[:200]})

        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    results["tests"].append(
                        {"raw_ssl": f"Connected with TLS {ssock.version()}"}
                    )
        except Exception as e:
            results["tests"].append({"raw_ssl_error": str(e)[:300]})

        try:
            import psycopg2

            for mode in ["disable", "require"]:
                try:
                    conn = psycopg2.connect(
                        host=hostname,
                        port=port,
                        dbname=parsed.path[1:],
                        user=parsed.username,
                        password=parsed.password,
                        sslmode=mode,
                    )
                    cur = conn.cursor()
                    cur.execute("SELECT 1;")
                    cur.close()
                    conn.close()
                    results["tests"].append({f"psycopg2_{mode}": "success"})
                except Exception as e:
                    results["tests"].append({f"psycopg2_{mode}": str(e)[:200]})
        except ImportError:
            results["tests"].append({"psycopg2": "not installed"})

        try:
            import psycopg

            for mode in ["disable", "require"]:
                try:
                    conn = psycopg.connect(
                        host=hostname,
                        port=port,
                        dbname=parsed.path[1:],
                        user=parsed.username,
                        password=parsed.password,
                        sslmode=mode,
                    )
                    cur = conn.cursor()
                    cur.execute("SELECT 1;")
                    cur.close()
                    conn.close()
                    results["tests"].append({f"psycopg_{mode}": "success"})
                except Exception as e:
                    results["tests"].append({f"psycopg_{mode}": str(e)[:200]})
        except ImportError:
            results["tests"].append({"psycopg": "not installed"})

    except Exception as e:
        results["error"] = str(e)

    return results
