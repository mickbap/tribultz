"""Reports router — PDF generation with audit hash, plan-gated."""

import hashlib
import json
import logging
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.plan_gate import require_plan
from app.database import get_db
from app.models.auth import User
from app.services.pdf_service import generate_validation_report_pdf, generate_batch_report_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

PDF_PLANS = ("profissional", "empresarial", "contador")


# ── Schemas ──────────────────────────────────────────────────────


class FindingSchema(BaseModel):
    rule_id: str
    severity: str  # ERROR | WARNING | INFO
    title: str
    where: str = "—"
    recommendation: str = "—"


class ValidationReportRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    cnpj: str = Field(..., min_length=14, max_length=18)
    reference_period: str = Field(..., description="Ex: 2026-03")
    job_id: str = Field(..., description="UUID do job de validação")
    findings: list[FindingSchema] = Field(default_factory=list)
    overall_status: str = Field(default="EM ANÁLISE")
    total_base: str = "0"
    total_cbs: str = "0"
    total_ibs: str = "0"
    cbs_rate: str = "0.10"
    ibs_rate: str = "0.90"


class BatchInvoiceSchema(BaseModel):
    nf_number: str
    cnpj_emitente: str
    valor_total: str
    status: str  # PASS | FAIL
    findings_count: int = 0


class BatchReportRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    cnpj: str = Field(..., min_length=14, max_length=18)
    reference_period: str
    job_id: str
    invoices: list[BatchInvoiceSchema] = Field(default_factory=list)
    overall_status: str = "EM ANÁLISE"


# ── Helpers ───────────────────────────────────────────────────────


def _compute_report_hash(payload: dict) -> str:
    """Deterministic SHA-256 fingerprint of the report input data."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _pdf_streaming_response(pdf_bytes: bytes, filename: str, report_hash: str) -> StreamingResponse:
    """Return a StreamingResponse with correct PDF headers."""
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "X-Report-Hash": report_hash,
            "X-PDF-SHA256": pdf_sha256,
            "Cache-Control": "no-store",
        },
    )


# ── Endpoints ─────────────────────────────────────────────────────


@router.post(
    "/pdf/validation",
    summary="Gerar relatório PDF de validação CBS/IBS",
    description=(
        "Gera um PDF auditável com findings, memória de cálculo CBS/IBS e hash de integridade. "
        "Disponível nos planos Profissional, Empresarial e Contador."
    ),
    dependencies=[Depends(require_plan(*PDF_PLANS))],
)
async def generate_validation_pdf(
    body: ValidationReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Generate a validation PDF report (plan-gated)."""
    findings_dicts = [f.model_dump() for f in body.findings]

    # Deterministic fingerprint of the validated content
    report_hash = _compute_report_hash({
        "job_id": body.job_id,
        "cnpj": body.cnpj,
        "reference_period": body.reference_period,
        "overall_status": body.overall_status,
        "total_cbs": body.total_cbs,
        "total_ibs": body.total_ibs,
        "findings": findings_dicts,
    })

    try:
        pdf_bytes = generate_validation_report_pdf(
            company_name=body.company_name,
            cnpj=body.cnpj,
            reference_period=body.reference_period,
            job_id=body.job_id,
            findings=findings_dicts,
            overall_status=body.overall_status,
            total_base=body.total_base,
            total_cbs=body.total_cbs,
            total_ibs=body.total_ibs,
            cbs_rate=body.cbs_rate,
            ibs_rate=body.ibs_rate,
            report_hash=report_hash,
        )
    except Exception:
        logger.exception("Erro ao gerar PDF de validação para job %s", body.job_id)
        raise HTTPException(status_code=500, detail="Erro ao gerar relatório PDF.")

    filename = f"tribultz_validacao_{body.job_id[:8]}.pdf"
    logger.info(
        "PDF validação gerado: job=%s user=%s bytes=%d hash=%s",
        body.job_id, cast(str, current_user.email), len(pdf_bytes), report_hash[:8],
    )
    return _pdf_streaming_response(pdf_bytes, filename, report_hash)


@router.post(
    "/pdf/batch",
    summary="Gerar relatório PDF de validação em lote",
    description=(
        "Gera um PDF auditável com resumo de múltiplas NF-es, taxa de aprovação e findings. "
        "Disponível nos planos Profissional, Empresarial e Contador."
    ),
    dependencies=[Depends(require_plan(*PDF_PLANS))],
)
async def generate_batch_pdf(
    body: BatchReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Generate a batch validation PDF report (plan-gated)."""
    invoices_dicts = [i.model_dump() for i in body.invoices]

    report_hash = _compute_report_hash({
        "job_id": body.job_id,
        "cnpj": body.cnpj,
        "reference_period": body.reference_period,
        "overall_status": body.overall_status,
        "invoices_count": len(invoices_dicts),
    })

    try:
        pdf_bytes = generate_batch_report_pdf(
            company_name=body.company_name,
            cnpj=body.cnpj,
            reference_period=body.reference_period,
            job_id=body.job_id,
            invoices=invoices_dicts,
            overall_status=body.overall_status,
            report_hash=report_hash,
        )
    except Exception:
        logger.exception("Erro ao gerar PDF em lote para job %s", body.job_id)
        raise HTTPException(status_code=500, detail="Erro ao gerar relatório PDF em lote.")

    filename = f"tribultz_lote_{body.job_id[:8]}.pdf"
    logger.info(
        "PDF lote gerado: job=%s user=%s docs=%d bytes=%d",
        body.job_id, cast(str, current_user.email), len(body.invoices), len(pdf_bytes),
    )
    return _pdf_streaming_response(pdf_bytes, filename, report_hash)
