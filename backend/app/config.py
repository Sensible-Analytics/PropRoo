from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "proproo-data"
    r2_endpoint: str = ""
    redis_url: str = ""
    data_dir: str = "/tmp"
    environment: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
