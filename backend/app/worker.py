"""Celery application instance."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "golden_config",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.device_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=300,
    result_expires=3600,
)
