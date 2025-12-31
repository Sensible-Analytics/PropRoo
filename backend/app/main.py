from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import sales

app = FastAPI(title="NSW Property Sales Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sales.router, prefix="/api", tags=["sales"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
