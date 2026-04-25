"""
Configuration — owned by tunjipaul.
"""
from pathlib import Path
from typing import Any, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file so it loads correctly regardless of
# the working directory (e.g. running uvicorn from the repo root).
_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # App
    APP_NAME: str = "SabiLens"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/sabilens"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    AUTH_AUTO_ACTIVATE: bool = True

    # RAG Service
    RAG_SERVICE_URL: str = "http://127.0.0.1:8001"
    RAG_SERVICE_TIMEOUT_SECONDS: float = 20.0

    # AI Service Endpoints
    AI_VISUAL_ENDPOINT: str = "http://localhost:8001/visual"
    AI_OCR_ENDPOINT: str = "http://localhost:8002/ocr"
    AI_REGULATORY_ENDPOINT: str = "http://localhost:8003/regulatory"
    AI_FUSION_ENDPOINT: str = "http://localhost:8004/fusion"

    # File Storage — Google Cloud Storage
    GCP_PROJECT_ID: Optional[str] = None
    GCS_BUCKET: Optional[str] = None           # scan images + product artwork (public-read)
    GCS_REPORTS_BUCKET: Optional[str] = None   # AI PDF reports (private, signed URLs)
    GCS_MODELS_BUCKET: Optional[str] = None    # ML/OCR model files (private)
    # Set GOOGLE_APPLICATION_CREDENTIALS to the path of your service account JSON key file.
    # If running on GCE/GKE/Cloud Run, leave unset — Workload Identity is used automatically.

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # GCS report bucket (private — 15-min signed URLs)
    GCS_REPORTS_BUCKET: str = "sabilens-report-prod"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _parse_debug(cls, value: Any) -> Any:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"release", "prod", "production"}:
                return False
            if lowered in {"dev", "development", "debug"}:
                return True
        return value

model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
