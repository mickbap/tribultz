"""Celery application – broker = Redis."""

from celery import Celery
from app.config import settings

celery = Celery(
    "tribultz",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    beat_schedule={},          # add periodic tasks here
)

# Auto-discover tasks
celery.autodiscover_tasks([
    "app.tasks.task_a_validate",
    "app.tasks.task_b_report",
    "app.tasks.task_c_simulation",
    "app.tasks.task_d_reconciliation",
    "app.tasks.task_e_hubspot",
])
