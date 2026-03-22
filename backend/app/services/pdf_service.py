"""PDF report generation — Jinja2 HTML templates rendered to PDF via WeasyPrint."""

import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
)


def _format_brl(value: Any) -> str:
    """Format a number as BRL currency: R$ 1.234,56"""
    try:
        d = Decimal(str(value)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        integer_part, decimal_part = str(d).split(".")
        # Add thousand separators
        integer_part = f"{int(integer_part):,}".replace(",", ".")
        return f"R$ {integer_part},{decimal_part}"
    except Exception:
        return f"R$ {value}"


_jinja_env.filters["brl"] = _format_brl


def generate_validation_report_pdf(
    *,
    company_name: str,
    cnpj: str,
    reference_period: str,
    job_id: str,
    findings: list[dict],
    overall_status: str,
    total_base: str = "0",
    total_cbs: str = "0",
    total_ibs: str = "0",
    cbs_rate: str = "0.10",
    ibs_rate: str = "0.90",
) -> bytes:
    """Render a validation report as PDF bytes.

    Falls back to HTML-only if WeasyPrint is not installed.
    """
    template = _jinja_env.get_template("report_validation.html")
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    # Categorize findings by severity
    errors = [f for f in findings if f.get("severity") == "ERROR"]
    warnings = [f for f in findings if f.get("severity") == "WARNING"]
    infos = [f for f in findings if f.get("severity") == "INFO"]

    html = template.render(
        company_name=company_name,
        cnpj=cnpj,
        reference_period=reference_period,
        job_id=job_id,
        generated_at=now,
        overall_status=overall_status,
        total_base=total_base,
        total_cbs=total_cbs,
        total_ibs=total_ibs,
        cbs_rate=cbs_rate,
        ibs_rate=ibs_rate,
        findings=findings,
        errors=errors,
        warnings=warnings,
        infos=infos,
        total_findings=len(findings),
    )

    try:
        from weasyprint import HTML
        pdf_bytes: bytes = HTML(string=html).write_pdf()  # type: ignore[assignment]
        logger.info("PDF generated for job %s (%d bytes)", job_id, len(pdf_bytes))
        return pdf_bytes
    except ImportError:
        logger.warning("WeasyPrint not installed, returning HTML as fallback")
        return html.encode("utf-8")


def generate_batch_report_pdf(
    *,
    company_name: str,
    cnpj: str,
    reference_period: str,
    job_id: str,
    invoices: list[dict],
    overall_status: str,
) -> bytes:
    """Render a batch validation report as PDF bytes."""
    template = _jinja_env.get_template("report_batch.html")
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    # Summary stats
    total = len(invoices)
    passed = sum(1 for inv in invoices if inv.get("status") == "PASS")
    failed = total - passed

    html = template.render(
        company_name=company_name,
        cnpj=cnpj,
        reference_period=reference_period,
        job_id=job_id,
        generated_at=now,
        overall_status=overall_status,
        invoices=invoices,
        total=total,
        passed=passed,
        failed=failed,
        pass_rate=f"{(passed / total * 100):.1f}" if total else "0",
    )

    try:
        from weasyprint import HTML
        pdf_bytes: bytes = HTML(string=html).write_pdf()  # type: ignore[assignment]
        logger.info("Batch PDF generated for job %s (%d bytes)", job_id, len(pdf_bytes))
        return pdf_bytes
    except ImportError:
        logger.warning("WeasyPrint not installed, returning HTML as fallback")
        return html.encode("utf-8")
