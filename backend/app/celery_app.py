"""Celery application – broker = Redis."""

from celery import Celery
from celery.schedules import crontab
from app.config import settings
from app.core.observability import init_sentry

# Error tracking nos processos worker/beat (no-op sem SENTRY_DSN).
# A API inicializa em app/main.py; aqui cobrimos as tasks de fundo.
init_sentry()

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
    worker_prefetch_multiplier=1,
    beat_schedule={
        "expire-trials-hourly": {
            "task": "billing.expire_trials",
            "schedule": crontab(minute="0"),  # every hour at :00
        },
        "warn-trial-expiring": {
            "task": "billing.warn_trial_expiring",
            "schedule": crontab(minute="30"),  # every hour at :30 (offset from expire)
        },
        "reset-usage-monthly": {
            "task": "billing.reset_monthly_usage",
            "schedule": crontab(minute="0", hour="0", day_of_month="1"),  # 1st of month at midnight
        },
        "classtrib-sync-weekly": {
            "task": "classtrib.sync_svrs",
            "schedule": crontab(minute="0", hour="0", day_of_week="0"),  # Sunday midnight
        },
        "compliance-monthly-scores": {
            "task": "compliance.compute_monthly_scores",
            "schedule": crontab(minute="0", hour="2", day_of_month="1"),  # 1st of month at 02:00
        },
        "crm-audit-daily": {
            "task": "crm.audit",
            "schedule": crontab(minute="0", hour="9"),  # daily at 09:00 BRT
        },
        "purge-expired-documents-monthly": {
            "task": "documents.purge_expired",
            "schedule": crontab(minute="30", hour="2", day_of_month="1"),  # 1st of month at 02:30
        },
    },
)

# Auto-discover tasks
celery.autodiscover_tasks([
    "app.tasks.task_a_validate",
    "app.tasks.task_b_report",
    "app.tasks.task_c_simulation",
    "app.tasks.task_d_reconciliation",
    "app.tasks.task_e_hubspot",
    "app.tasks.task_g_billing",
    "app.tasks.task_h_sped",
    "app.tasks.task_i_compliance",
    "app.tasks.task_j_retention",
    "app.tasks.task_crm",
])
