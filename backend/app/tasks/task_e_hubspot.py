"""Task E – HubSpot sync: create/update deal + register readiness score."""

import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from app.celery_app import celery
from app.config import settings
from app.tools.postgres_tool import get_tax_rules, insert_audit_log
from app.tools.hubspot_tool import upsert_company, upsert_deal, log_note

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")


def _compute_readiness_score(
    has_cbs_rule: bool,
    has_ibs_rule: bool,
    invoices_validated: int,
    exceptions_count: int,
) -> int:
    """
    Simple readiness score 0-100:
      - 30 pts for having CBS rule configured
      - 30 pts for having IBS rule configured
      - 30 pts for validated invoices (max 30 after 10+)
      - -10 pts per unresolved exception (min 0 total)
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
) -> dict:
    """
    1. Check current CBS/IBS rule status
    2. Compute readiness score
    3. Upsert company in HubSpot
    4. Create/update deal with readiness score
    5. Log a note summarising the sync
    6. Audit-log the operation
    """
    ref = date.today()

    # 1. Check rules
    rules = get_tax_rules(tenant_id, ["STD_CBS", "STD_IBS"], ref)
    rule_types = {r["tax_type"] for r in rules}
    has_cbs = "CBS" in rule_types
    has_ibs = "IBS" in rule_types

    # 2. Readiness score
    score = _compute_readiness_score(has_cbs, has_ibs, invoices_validated, exceptions_count)

    # 3. Upsert company
    company_result = upsert_company(
        name=company_name,
        domain=domain,
        properties={
            "tribultz_cnpj": cnpj,
            "tribultz_readiness_score": str(score),
            "tribultz_tenant": tenant_slug,
        },
    )

    # 4. Create deal
    deal_name = f"Tribultz – {company_name} ({tenant_slug})"
    deal_result = upsert_deal(
        deal_name=deal_name,
        stage="appointmentscheduled",
        amount=float(deal_value) if deal_value else None,
        properties={
            "tribultz_readiness_score": str(score),
            "description": (
                f"Readiness Score: {score}/100 | "
                f"CBS: {'✓' if has_cbs else '✗'} | IBS: {'✓' if has_ibs else '✗'} | "
                f"Invoices: {invoices_validated} | Exceptions: {exceptions_count}"
            ),
        },
    )

    # 5. Log note
    note_body = (
        f"🔄 Tribultz Sync – {ref.isoformat()}\n\n"
        f"Readiness Score: {score}/100\n"
        f"CBS configurado: {'Sim' if has_cbs else 'Não'}\n"
        f"IBS configurado: {'Sim' if has_ibs else 'Não'}\n"
        f"Notas validadas: {invoices_validated}\n"
        f"Exceções abertas: {exceptions_count}\n"
    )

    company_id = company_result.get("id", "")
    if company_id and settings.HUBSPOT_ENABLED:
        log_note(object_type="companies", object_id=company_id, body=note_body)

    # 6. Audit
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

    logger.info("Task E [%s] score=%d hubspot=%s", tenant_slug, score, settings.HUBSPOT_ENABLED)
    return result
