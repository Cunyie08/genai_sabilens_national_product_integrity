"""
Configuration — owned by tunjipaul.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/sabilens"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RAG_SERVICE_URL: str = "http://127.0.0.1:8001"
    RAG_SERVICE_TIMEOUT_SECONDS: float = 20.0

    class Config:
        env_file = ".env"


settings = Settings()
