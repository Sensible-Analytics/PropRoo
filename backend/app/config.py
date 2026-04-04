from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    data_dir: str = "/tmp"
    environment: str = "development"

    # Cloudflare R2 settings (optional — if set, DuckDB reads parquet directly from R2)
    r2_bucket_name: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[str] = None
    r2_endpoint: Optional[str] = None

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
