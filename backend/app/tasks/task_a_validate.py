"""Task A – Validate CBS/IBS for a batch of items and write audit_log."""

import json
import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from app.celery_app import celery
from app.tools.postgres_tool import get_tax_rules, insert_audit_log

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")


@celery.task(name="task_a_validate_cbs_ibs", bind=True, max_retries=3)
def task_a_validate_cbs_ibs(
    self,
    tenant_id: str,
    tenant_slug: str,
    invoice_number: str,
    issue_date: str,
    declared_cbs: str,
    declared_ibs: str,
    items: list[dict],
) -> dict:
    """
    1. Look up CBS & IBS rules from Postgres via PostgresTool
    2. Calculate expected taxes per item
    3. Compare declared vs calculated
    4. Log the result (PASS / FAIL) into audit_log
    5. Return detailed result
    """
    ref_date = date.fromisoformat(issue_date)

    # Collect unique rule codes
    all_codes = set()
    for it in items:
        all_codes.add(it.get("cbs_rule_code", "STD_CBS"))
        all_codes.add(it.get("ibs_rule_code", "STD_IBS"))

    # Fetch rules once
    rules = get_tax_rules(tenant_id, list(all_codes), ref_date)
    rate_map: dict[tuple[str, str], Decimal] = {
        (r["rule_code"], r["tax_type"]): Decimal(str(r["rate"]))
        for r in rules
    }

    # Calculate per item
    total_cbs = Decimal("0")
    total_ibs = Decimal("0")
    item_results: list[dict] = []

    for it in items:
        base = Decimal(str(it["base_amount"]))
        cbs_code = it.get("cbs_rule_code", "STD_CBS")
        ibs_code = it.get("ibs_rule_code", "STD_IBS")

        cbs_rate = rate_map.get((cbs_code, "CBS"), Decimal("0"))
        ibs_rate = rate_map.get((ibs_code, "IBS"), Decimal("0"))

        cbs_amt = (base * cbs_rate).quantize(TWO_PLACES, ROUND_HALF_UP)
        ibs_amt = (base * ibs_rate).quantize(TWO_PLACES, ROUND_HALF_UP)

        total_cbs += cbs_amt
        total_ibs += ibs_amt

        item_results.append({
            "sku": it.get("sku", ""),
            "base_amount": str(base),
            "cbs_rate": str(cbs_rate),
            "cbs_amount": str(cbs_amt),
            "ibs_rate": str(ibs_rate),
            "ibs_amount": str(ibs_amt),
        })

    total_cbs = total_cbs.quantize(TWO_PLACES, ROUND_HALF_UP)
    total_ibs = total_ibs.quantize(TWO_PLACES, ROUND_HALF_UP)
    decl_cbs = Decimal(declared_cbs).quantize(TWO_PLACES, ROUND_HALF_UP)
    decl_ibs = Decimal(declared_ibs).quantize(TWO_PLACES, ROUND_HALF_UP)

    cbs_match = total_cbs == decl_cbs
    ibs_match = total_ibs == decl_ibs
    status = "PASS" if (cbs_match and ibs_match) else "FAIL"

    result = {
        "status": status,
        "invoice_number": invoice_number,
        "issue_date": issue_date,
        "declared_cbs": str(decl_cbs),
        "declared_ibs": str(decl_ibs),
        "calculated_cbs": str(total_cbs),
        "calculated_ibs": str(total_ibs),
        "cbs_match": cbs_match,
        "ibs_match": ibs_match,
        "items": item_results,
    }

    # Audit trail
    audit = insert_audit_log(
        tenant_id=tenant_id,
        action=f"validation_{status.lower()}",
        entity_type="invoice",
        entity_id=invoice_number,
        payload=result,
    )
    result["audit_id"] = audit["id"]
    result["audit_checksum"] = audit["checksum"]

    logger.info("Task A [%s] invoice=%s status=%s", tenant_slug, invoice_number, status)
    return result
