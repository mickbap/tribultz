"""PDF report generation — Jinja2 HTML templates rendered to PDF via WeasyPrint."""

import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Armazenamento permanece UTC (datetime.now(timezone.utc)) — conversão para
# America/Sao_Paulo acontece só na borda de apresentação do laudo, nunca no
# storage. Ver knowledge/engineering/tempo-e-auditoria.md no Brain.
BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")


def _format_brasilia(instant_utc: datetime) -> str:
    """Converte um instante UTC aware para string de exibição em America/Sao_Paulo."""
    return instant_utc.astimezone(BRASILIA_TZ).strftime("%d/%m/%Y %H:%M horário de Brasília")


def _generated_at_brasilia() -> str:
    return _format_brasilia(datetime.now(timezone.utc))


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


def _persist_to_s3(key: str, data: bytes, content_type: str) -> None:
    """Upload bytes to S3/MinIO. Silently logs on failure."""
    try:
        from app.tools import s3_tool
        s3_tool.put_object(key=key, data=data, content_type=content_type)
    except Exception:
        logger.warning("S3 persist failed for key=%s", key, exc_info=True)


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
    report_hash: str = "",
    storage_key: str = "",
) -> dict:
    """Render a validation report as PDF bytes and optionally persist to S3.

    Returns a dict with keys: bytes, storage_key, file_size.
    Falls back to HTML-only if WeasyPrint is not installed.
    """
    template = _jinja_env.get_template("report_validation.html")
    now = _generated_at_brasilia()

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
        report_hash=report_hash,
    )

    try:
        from weasyprint import HTML
        pdf_bytes: bytes = HTML(string=html).write_pdf()  # type: ignore[assignment]
        logger.info("PDF generated for job %s (%d bytes)", job_id, len(pdf_bytes))
        if storage_key:
            _persist_to_s3(storage_key, pdf_bytes, "application/pdf")
    except (ImportError, OSError):
        logger.warning("WeasyPrint unavailable (missing GTK/system libs), returning HTML fallback")
        pdf_bytes = html.encode("utf-8")
        if storage_key:
            # Use .html extension for fallback
            html_key = storage_key.replace(".pdf", ".html") if storage_key.endswith(".pdf") else storage_key + ".html"
            _persist_to_s3(html_key, pdf_bytes, "text/html")

    return {
        "bytes": pdf_bytes,
        "storage_key": storage_key,
        "file_size": len(pdf_bytes),
    }


def generate_credit_report_pdf(
    *,
    company_name: str,
    cnpj: str,
    period_type: str,
    periods: list[dict],
    storage_key: str = "",
) -> dict:
    """Render the credit dashboard (#258) as a PDF with per-document (NF) audit
    trail — cada período traz a lista de documentos que compõem o saldo.

    Returns a dict with keys: bytes, storage_key, file_size.
    Falls back to HTML-only if WeasyPrint is not installed.
    """
    template = _jinja_env.get_template("report_credits.html")
    now = _generated_at_brasilia()

    def _sum(key: str) -> float:
        total = 0.0
        for p in periods:
            try:
                total += float(p.get(key, 0) or 0)
            except (TypeError, ValueError):
                pass
        return total

    html = template.render(
        company_name=company_name,
        cnpj=cnpj,
        period_type="Mensal" if period_type == "month" else "Trimestral",
        generated_at=now,
        periods=periods,
        total_generated=_sum("generated_total"),
        total_apropriated=_sum("apropriated_total"),
        total_available=_sum("available_total"),
        total_at_risk=_sum("at_risk_total"),
    )

    try:
        from weasyprint import HTML
        pdf_bytes: bytes = HTML(string=html).write_pdf()  # type: ignore[assignment]
        logger.info("Credit report PDF generated (%d bytes)", len(pdf_bytes))
        if storage_key:
            _persist_to_s3(storage_key, pdf_bytes, "application/pdf")
    except (ImportError, OSError):
        logger.warning("WeasyPrint unavailable (missing GTK/system libs), returning HTML fallback")
        pdf_bytes = html.encode("utf-8")
        if storage_key:
            html_key = storage_key.replace(".pdf", ".html") if storage_key.endswith(".pdf") else storage_key + ".html"
            _persist_to_s3(html_key, pdf_bytes, "text/html")

    return {
        "bytes": pdf_bytes,
        "storage_key": storage_key,
        "file_size": len(pdf_bytes),
    }


def generate_batch_report_pdf(
    *,
    company_name: str,
    cnpj: str,
    reference_period: str,
    job_id: str,
    invoices: list[dict],
    overall_status: str,
    report_hash: str = "",
    storage_key: str = "",
) -> dict:
    """Render a batch validation report as PDF bytes and optionally persist to S3.

    Returns a dict with keys: bytes, storage_key, file_size.
    """
    template = _jinja_env.get_template("report_batch.html")
    now = _generated_at_brasilia()

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
        report_hash=report_hash,
    )

    try:
        from weasyprint import HTML
        pdf_bytes: bytes = HTML(string=html).write_pdf()  # type: ignore[assignment]
        logger.info("Batch PDF generated for job %s (%d bytes)", job_id, len(pdf_bytes))
        if storage_key:
            _persist_to_s3(storage_key, pdf_bytes, "application/pdf")
    except (ImportError, OSError):
        logger.warning("WeasyPrint unavailable (missing GTK/system libs), returning HTML fallback")
        pdf_bytes = html.encode("utf-8")
        if storage_key:
            html_key = storage_key.replace(".pdf", ".html") if storage_key.endswith(".pdf") else storage_key + ".html"
            _persist_to_s3(html_key, pdf_bytes, "text/html")

    return {
        "bytes": pdf_bytes,
        "storage_key": storage_key,
        "file_size": len(pdf_bytes),
    }
