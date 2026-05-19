"""
SafeReach — Celery Application + Task Definitions
Async tasks: AI inference, SMS, hospital pre-alert, hotspot refresh.
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "safereach",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.ai_tasks", "app.tasks.notification_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "refresh-hotspot-predictions": {
            "task": "app.tasks.ai_tasks.refresh_hotspot_grid",
            "schedule": settings.HOTSPOT_REFRESH_HOURS * 3600,
        },
    },
)
