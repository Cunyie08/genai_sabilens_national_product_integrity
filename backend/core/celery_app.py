"""Celery task queue configuration."""
from celery import Celery
from backend.config import settings

celery_app = Celery(
    "sabilens",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["backend.admin.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Africa/Lagos",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=30 * 60,
    beat_schedule={
        "refresh-enforcement-cases": {
            "task": "backend.admin.tasks.refresh_enforcement_cases",
            "schedule": 6 * 3600,
        },
        "daily-analytics-aggregation": {
            "task": "backend.admin.tasks.daily_analytics_aggregation",
            "schedule": 86400,
        },
    },
)
