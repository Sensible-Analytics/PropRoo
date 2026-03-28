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

    results = {"tests": []}

    try:
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            conn = psycopg2.connect(DATABASE_URL, ssl_context=context)
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            cur.close()
            conn.close()
            results["tests"].append({"ssl_context_CERT_NONE": "success"})
        except Exception as e:
            results["tests"].append({"ssl_context_CERT_NONE": str(e)[:300]})

        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            conn = psycopg2.connect(DATABASE_URL, ssl_context=context)
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            cur.close()
            conn.close()
            results["tests"].append({"SSL_CONTEXT_TLS_CLIENT": "success"})
        except Exception as e:
            results["tests"].append({"SSL_CONTEXT_TLS_CLIENT": str(e)[:300]})

    except Exception as e:
        results["error"] = str(e)

    return results
