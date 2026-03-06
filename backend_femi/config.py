"""
Configuration — owned by tunjipaul.
"""
from pathlib import Path
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite+aiosqlite:///{(BASE_DIR / 'app.db').as_posix()}"
    SECRET_KEY: str = "change-me-in-production"
    NAFDAC_BOOTSTRAP_KEY: str = "change-me-bootstrap-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RAG_SERVICE_URL: str = "http://127.0.0.1:8001"
    RAG_SERVICE_TIMEOUT_SECONDS: float = 20.0

    class Config:
        env_file = ".env"


settings = Settings()
