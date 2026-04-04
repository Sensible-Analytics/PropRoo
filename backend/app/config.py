from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: str = "/tmp"
    environment: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
