"""Task B – Generate compliance report (Markdown) and save to MinIO."""

import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app.celery_app import celery
from app.tools.postgres_tool import get_tax_rules, insert_audit_log, persist_artifact_metadata
from app.tools.s3_tool import put_object, get_object_url

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")


@celery.task(name="task_b_compliance_report", bind=True, max_retries=3)
def task_b_compliance_report(
    self,
    tenant_id: str,
    tenant_slug: str,
    company_name: str,
    cnpj: str,
    reference_period: str,          # "YYYY-MM"
    invoices: list[dict],           # [{invoice_number, items: [{base, cbs, ibs}]}]
) -> dict:
    """
    1. Iterate invoices and validate each against active rules
    2. Build a Markdown compliance report
    3. Upload to MinIO via S3Tool
    4. Persist artifact metadata + audit_log
    5. Return {report_url, checksum, summary}
    """
    ref_date = date.fromisoformat(f"{reference_period}-01")
    now_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Fetch all active rules once
    rules = get_tax_rules(tenant_id, ["STD_CBS", "STD_IBS"], ref_date)
    rate_map = {r["tax_type"]: Decimal(str(r["rate"])) for r in rules}
    cbs_rate = rate_map.get("CBS", Decimal("0"))
    ibs_rate = rate_map.get("IBS", Decimal("0"))

    # ── Build report ──────────────────────────────────────────
    lines: list[str] = []
    lines.append(f"# Relatório de Conformidade Tributária")
    lines.append(f"")
    lines.append(f"**Empresa:** {company_name}  ")
    lines.append(f"**CNPJ:** {cnpj}  ")
    lines.append(f"**Período:** {reference_period}  ")
    lines.append(f"**Gerado em:** {now_str}  ")
    lines.append(f"**Alíquota CBS:** {cbs_rate}  ")
    lines.append(f"**Alíquota IBS:** {ibs_rate}  ")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## Resumo por Nota Fiscal")
    lines.append(f"")
    lines.append(f"| NF | Base Total | CBS Esperado | IBS Esperado | Status |")
    lines.append(f"|---|---|---|---|---|")

    total_base = Decimal("0")
    total_cbs = Decimal("0")
    total_ibs = Decimal("0")
    all_pass = True
    invoice_details: list[dict] = []

    for inv in invoices:
        inv_num = inv.get("invoice_number", "?")
        inv_base = Decimal("0")
        inv_cbs_calc = Decimal("0")
        inv_ibs_calc = Decimal("0")
        inv_cbs_decl = Decimal(str(inv.get("declared_cbs", "0")))
        inv_ibs_decl = Decimal(str(inv.get("declared_ibs", "0")))

        for it in inv.get("items", []):
            base = Decimal(str(it.get("base_amount", "0")))
            inv_base += base
            inv_cbs_calc += (base * cbs_rate).quantize(TWO_PLACES, ROUND_HALF_UP)
            inv_ibs_calc += (base * ibs_rate).quantize(TWO_PLACES, ROUND_HALF_UP)

        inv_cbs_calc = inv_cbs_calc.quantize(TWO_PLACES, ROUND_HALF_UP)
        inv_ibs_calc = inv_ibs_calc.quantize(TWO_PLACES, ROUND_HALF_UP)

        cbs_ok = abs(inv_cbs_calc - inv_cbs_decl.quantize(TWO_PLACES)) <= TWO_PLACES
        ibs_ok = abs(inv_ibs_calc - inv_ibs_decl.quantize(TWO_PLACES)) <= TWO_PLACES
        status = "✅ PASS" if (cbs_ok and ibs_ok) else "❌ FAIL"
        if not (cbs_ok and ibs_ok):
            all_pass = False

        lines.append(f"| {inv_num} | {inv_base} | {inv_cbs_calc} | {inv_ibs_calc} | {status} |")

        total_base += inv_base
        total_cbs += inv_cbs_calc
        total_ibs += inv_ibs_calc

        invoice_details.append({
            "invoice_number": inv_num,
            "base": str(inv_base),
            "cbs_calculated": str(inv_cbs_calc),
            "ibs_calculated": str(inv_ibs_calc),
            "status": "PASS" if (cbs_ok and ibs_ok) else "FAIL",
        })

    lines.append(f"")
    lines.append(f"## Totais")
    lines.append(f"")
    lines.append(f"- **Base total:** R$ {total_base}")
    lines.append(f"- **CBS total:** R$ {total_cbs}")
    lines.append(f"- **IBS total:** R$ {total_ibs}")
    lines.append(f"- **Resultado geral:** {'✅ CONFORME' if all_pass else '❌ NÃO CONFORME'}")
    lines.append(f"")

    report_md = "\n".join(lines)
    report_bytes = report_md.encode("utf-8")

    # ── Upload to MinIO ──────────────────────────────────────
    s3_key = f"reports/{tenant_slug}/{reference_period}/compliance_{now_str}.md"
    upload = put_object(
        key=s3_key,
        data=report_bytes,
        content_type="text/markdown; charset=utf-8",
        metadata={"tenant": tenant_slug, "period": reference_period},
    )

    report_url = get_object_url(s3_key, expires_in=86400)

    # ── Artifact metadata + audit ────────────────────────────
    persist_artifact_metadata(
        tenant_id=tenant_id,
        entity_type="compliance_report",
        entity_id=f"{tenant_slug}/{reference_period}",
        artifact_type="markdown_report",
        storage_key=s3_key,
        checksum=upload["checksum_sha256"],
        metadata={"invoices_checked": len(invoices), "overall": "CONFORME" if all_pass else "NAO_CONFORME"},
    )

    audit = insert_audit_log(
        tenant_id=tenant_id,
        action="compliance_report_generated",
        entity_type="compliance_report",
        entity_id=f"{tenant_slug}/{reference_period}",
        payload={"s3_key": s3_key, "overall": "CONFORME" if all_pass else "NAO_CONFORME"},
    )

    result = {
        "status": "CONFORME" if all_pass else "NAO_CONFORME",
        "report_url": report_url,
        "s3_key": s3_key,
        "checksum": upload["checksum_sha256"],
        "invoices_checked": len(invoices),
        "total_base": str(total_base),
        "total_cbs": str(total_cbs),
        "total_ibs": str(total_ibs),
        "audit_id": audit["id"],
        "details": invoice_details,
    }

    logger.info("Task B [%s] report=%s status=%s", tenant_slug, s3_key, result["status"])
    return result
