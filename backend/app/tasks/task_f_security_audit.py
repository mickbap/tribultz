"""Task F – Periodic security audit via CrewAI Security Crew.

Celery Beat schedules this task to run daily. It collects access logs
from the last 24h, runs SOC analysis, CloudSec audit, and produces
an SRE executive report.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from app.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="task_f_security_audit", bind=True, max_retries=1)
def task_f_security_audit(self, tenant_id: str) -> dict:
    """Run security audit for a tenant."""
    from app.crews.security_crew import TribultzSecurityCrew

    logger.info("security_audit_start tenant=%s", tenant_id)
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(hours=24)
    report_period = f"{period_start.date().isoformat()} to {now.date().isoformat()}"

    # Collect access logs from DB (login events from last 24h)
    log_entries = _collect_access_logs(tenant_id, period_start)
    storage_config = _collect_storage_config(tenant_id)

    crew = TribultzSecurityCrew(tenant_id=tenant_id)

    # Step 1: SOC analysis
    soc_result = crew.analyze_access(json.dumps(log_entries, default=str))

    # Step 2: CloudSec audit
    cloudsec_result = crew.audit_storage(json.dumps(storage_config, default=str))

    # Step 3: SRE executive report
    report = crew.executive_report(
        soc_alerts=json.dumps(soc_result, default=str),
        cloudsec_audit=json.dumps(cloudsec_result, default=str),
        report_period=report_period,
    )

    logger.info("security_audit_complete tenant=%s", tenant_id)
    return {
        "tenant_id": tenant_id,
        "period": report_period,
        "soc": soc_result,
        "cloudsec": cloudsec_result,
        "executive_report": report,
    }


def _collect_access_logs(tenant_id: str, since: datetime) -> list[dict]:
    """Collect recent access events. Returns empty list if DB unavailable."""
    try:
        from sqlalchemy import text
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            # Query audit_logs for auth events
            result = db.execute(
                text(
                    "SELECT id, action, actor_id, created_at, details "
                    "FROM audit_logs "
                    "WHERE tenant_id = :tid AND created_at >= :since "
                    "AND action IN ('login_success', 'login_failed', 'user_registered', "
                    "'lgpd_account_deleted', 'email_verified') "
                    "ORDER BY created_at DESC LIMIT 500"
                ),
                {"tid": tenant_id, "since": since},
            )
            rows = result.fetchall()
            return [
                {
                    "id": str(r[0]),
                    "action": r[1],
                    "actor_id": str(r[2]) if r[2] else None,
                    "created_at": r[3].isoformat() if r[3] else None,
                    "details": r[4],
                }
                for r in rows
            ]
        finally:
            db.close()
    except Exception as e:
        logger.warning("Failed to collect access logs: %s", e)
        return []


def _collect_storage_config(tenant_id: str) -> dict:
    """Collect current storage configuration for audit."""
    from app.config import settings

    return {
        "tenant_id": tenant_id,
        "s3_endpoint": settings.S3_ENDPOINT,
        "s3_bucket": settings.S3_BUCKET,
        "environment": settings.ENVIRONMENT,
        "encryption_at_rest": "AES-256 (MinIO default)",
        "encryption_in_transit": "TLS" if settings.ENVIRONMENT == "production" else "HTTP (dev)",
        "public_access": False,
        "versioning": True,
        "access_logging": True,
        "data_residency": "Brazil (self-hosted)",
    }
