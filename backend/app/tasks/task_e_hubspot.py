"""Task E - HubSpot sync: create/update deal and register readiness score."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from app.celery_app import celery
from app.config import settings
from app.tools.hubspot_tool import log_note, upsert_company, upsert_deal
from app.tools.postgres_tool import get_tax_rules, insert_audit_log, job_status_update

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")


def _compute_readiness_score(
    has_cbs_rule: bool,
    has_ibs_rule: bool,
    invoices_validated: int,
    exceptions_count: int,
) -> int:
    """
    Simple readiness score 0-100.
    """
    score = 0
    if has_cbs_rule:
        score += 30
    if has_ibs_rule:
        score += 30
    score += min(30, invoices_validated * 3)
    score -= exceptions_count * 10
    return max(0, min(100, score))


@celery.task(name="task_e_hubspot_sync", bind=True, max_retries=3)
def task_e_hubspot_sync(
    self,
    tenant_id: str,
    tenant_slug: str,
    company_name: str,
    cnpj: str,
    domain: str | None = None,
    invoices_validated: int = 0,
    exceptions_count: int = 0,
    deal_value: str | None = None,
    transaction_id: str | None = None,
) -> dict:
    """
    1. Check current CBS/IBS rule status
    2. Compute readiness score
    3. Upsert company in HubSpot
    4. Create/update deal with readiness score
    5. Log a note summarising the sync
    6. Audit-log the operation
    """
    task_id = str(self.request.id) if self.request and self.request.id else ""
    if task_id:
        job_status_update(job_id=task_id, status="RUNNING", transaction_id=transaction_id)

    try:
        ref = date.today()

        rules = get_tax_rules(tenant_id, ["STD_CBS", "STD_IBS"], ref)
        rule_types = {rule["tax_type"] for rule in rules}
        has_cbs = "CBS" in rule_types
        has_ibs = "IBS" in rule_types

        score = _compute_readiness_score(
            has_cbs,
            has_ibs,
            invoices_validated,
            exceptions_count,
        )

        company_result = upsert_company(
            name=company_name,
            domain=domain,
            properties={
                "tribultz_cnpj": cnpj,
                "tribultz_readiness_score": str(score),
                "tribultz_tenant": tenant_slug,
            },
        )

        deal_name = f"Tribultz - {company_name} ({tenant_slug})"
        deal_result = upsert_deal(
            deal_name=deal_name,
            stage="appointmentscheduled",
            amount=float(deal_value) if deal_value else None,
            properties={
                "tribultz_readiness_score": str(score),
                "description": (
                    f"Readiness Score: {score}/100 | "
                    f"CBS: {'yes' if has_cbs else 'no'} | "
                    f"IBS: {'yes' if has_ibs else 'no'} | "
                    f"Invoices: {invoices_validated} | "
                    f"Exceptions: {exceptions_count}"
                ),
            },
        )

        note_body = (
            f"Tribultz Sync - {ref.isoformat()}\n\n"
            f"Readiness Score: {score}/100\n"
            f"CBS configurado: {'Sim' if has_cbs else 'Nao'}\n"
            f"IBS configurado: {'Sim' if has_ibs else 'Nao'}\n"
            f"Notas validadas: {invoices_validated}\n"
            f"Excecoes abertas: {exceptions_count}\n"
        )

        company_id = company_result.get("id", "")
        if company_id and settings.HUBSPOT_ENABLED:
            log_note(object_type="companies", object_id=company_id, body=note_body)

        audit = insert_audit_log(
            tenant_id=tenant_id,
            action="hubspot_sync",
            entity_type="hubspot_deal",
            entity_id=deal_result.get("id", ""),
            payload={
                "readiness_score": score,
                "company": company_name,
                "hubspot_enabled": settings.HUBSPOT_ENABLED,
            },
        )

        result = {
            "readiness_score": score,
            "hubspot_enabled": settings.HUBSPOT_ENABLED,
            "company": company_result,
            "deal": deal_result,
            "audit_id": audit["id"],
        }

        if task_id:
            job_status_update(
                job_id=task_id,
                status="SUCCESS",
                result=result,
                transaction_id=transaction_id,
            )

        logger.info("Task E [%s] score=%d hubspot=%s", tenant_slug, score, settings.HUBSPOT_ENABLED)
        return result
    except Exception as exc:
        if task_id:
            job_status_update(
                job_id=task_id,
                status="FAILED",
                error_message=str(exc),
                transaction_id=transaction_id,
            )
        raise
