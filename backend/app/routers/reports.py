"""Reports router — PDF generation with S3 persistence, audit hash, and presigned download."""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.plan_gate import require_plan
from app.database import get_db
from app.models.auth import User
from app.models.reports import Report
from app.services.pdf_service import generate_validation_report_pdf, generate_batch_report_pdf
from app.tools import s3_tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

PDF_PLANS = ("profissional", "empresarial", "contador")

_PRESIGNED_TTL = 900  # 15 minutes


# ── Request Schemas ────────────────────────────────────────────────


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


# ── Response Schemas ───────────────────────────────────────────────


class ReportCreatedResponse(BaseModel):
    report_id: UUID
    download_url: str
    expires_at: datetime
    report_hash: str
    file_size: int


class ReportListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    report_type: str
    job_id: Optional[str]
    report_hash: str
    file_size: Optional[int]
    status: str
    created_at: datetime


class DownloadResponse(BaseModel):
    download_url: str
    expires_at: datetime


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
    response_model=None,
)
async def generate_validation_pdf(
    body: ValidationReportRequest,
    stream: bool = Query(default=False, description="Se true, retorna StreamingResponse (legado)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportCreatedResponse | StreamingResponse:
    """Generate a validation PDF report (plan-gated).

    When stream=true falls back to the legacy StreamingResponse (no persistence).
    """
    findings_dicts = [f.model_dump() for f in body.findings]

    report_hash = _compute_report_hash({
        "job_id": body.job_id,
        "cnpj": body.cnpj,
        "reference_period": body.reference_period,
        "overall_status": body.overall_status,
        "total_cbs": body.total_cbs,
        "total_ibs": body.total_ibs,
        "findings": findings_dicts,
    })

    if stream:
        # Legacy streaming path — no S3 persistence
        try:
            result = generate_validation_report_pdf(
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
            logger.exception("Erro ao gerar PDF de validação (stream) para job %s", body.job_id)
            raise HTTPException(status_code=500, detail="Erro ao gerar relatório PDF.")
        filename = f"tribultz_validacao_{body.job_id[:8]}.pdf"
        return _pdf_streaming_response(result["bytes"], filename, report_hash)

    # S3-persisted path
    storage_key = f"reports/{current_user.tenant_id}/validation/{uuid4()}.pdf"

    try:
        result = generate_validation_report_pdf(
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
            storage_key=storage_key,
        )
    except Exception:
        logger.exception("Erro ao gerar PDF de validação para job %s", body.job_id)
        raise HTTPException(status_code=500, detail="Erro ao gerar relatório PDF.")

    # Persist Report record
    report = Report(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        job_id=body.job_id,
        report_type="validation",
        storage_key=result["storage_key"],
        file_size=result["file_size"],
        report_hash=report_hash,
        status="ready",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Generate presigned download URL
    try:
        download_url = s3_tool.get_object_url(key=result["storage_key"], expires_in=_PRESIGNED_TTL)
    except Exception:
        logger.exception("Erro ao gerar URL presigned para storage_key=%s", result["storage_key"])
        raise HTTPException(status_code=503, detail="Erro ao gerar URL de download.")

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_PRESIGNED_TTL)
    logger.info(
        "PDF validação persistido: job=%s user=%s bytes=%d hash=%s",
        body.job_id, cast(str, current_user.email), result["file_size"], report_hash[:8],
    )
    return ReportCreatedResponse(
        report_id=report.id,
        download_url=download_url,
        expires_at=expires_at,
        report_hash=report_hash,
        file_size=result["file_size"],
    )


@router.post(
    "/pdf/batch",
    summary="Gerar relatório PDF de validação em lote",
    description=(
        "Gera um PDF auditável com resumo de múltiplas NF-es, taxa de aprovação e findings. "
        "Disponível nos planos Profissional, Empresarial e Contador."
    ),
    dependencies=[Depends(require_plan(*PDF_PLANS))],
    response_model=None,
)
async def generate_batch_pdf(
    body: BatchReportRequest,
    stream: bool = Query(default=False, description="Se true, retorna StreamingResponse (legado)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportCreatedResponse | StreamingResponse:
    """Generate a batch validation PDF report (plan-gated).

    When stream=true falls back to the legacy StreamingResponse (no persistence).
    """
    invoices_dicts = [i.model_dump() for i in body.invoices]

    report_hash = _compute_report_hash({
        "job_id": body.job_id,
        "cnpj": body.cnpj,
        "reference_period": body.reference_period,
        "overall_status": body.overall_status,
        "invoices_count": len(invoices_dicts),
    })

    if stream:
        try:
            result = generate_batch_report_pdf(
                company_name=body.company_name,
                cnpj=body.cnpj,
                reference_period=body.reference_period,
                job_id=body.job_id,
                invoices=invoices_dicts,
                overall_status=body.overall_status,
                report_hash=report_hash,
            )
        except Exception:
            logger.exception("Erro ao gerar PDF em lote (stream) para job %s", body.job_id)
            raise HTTPException(status_code=500, detail="Erro ao gerar relatório PDF em lote.")
        filename = f"tribultz_lote_{body.job_id[:8]}.pdf"
        return _pdf_streaming_response(result["bytes"], filename, report_hash)

    storage_key = f"reports/{current_user.tenant_id}/batch/{uuid4()}.pdf"

    try:
        result = generate_batch_report_pdf(
            company_name=body.company_name,
            cnpj=body.cnpj,
            reference_period=body.reference_period,
            job_id=body.job_id,
            invoices=invoices_dicts,
            overall_status=body.overall_status,
            report_hash=report_hash,
            storage_key=storage_key,
        )
    except Exception:
        logger.exception("Erro ao gerar PDF em lote para job %s", body.job_id)
        raise HTTPException(status_code=500, detail="Erro ao gerar relatório PDF em lote.")

    report = Report(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        job_id=body.job_id,
        report_type="batch",
        storage_key=result["storage_key"],
        file_size=result["file_size"],
        report_hash=report_hash,
        status="ready",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    try:
        download_url = s3_tool.get_object_url(key=result["storage_key"], expires_in=_PRESIGNED_TTL)
    except Exception:
        logger.exception("Erro ao gerar URL presigned para storage_key=%s", result["storage_key"])
        raise HTTPException(status_code=503, detail="Erro ao gerar URL de download.")

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_PRESIGNED_TTL)
    logger.info(
        "PDF lote persistido: job=%s user=%s docs=%d bytes=%d",
        body.job_id, cast(str, current_user.email), len(body.invoices), result["file_size"],
    )
    return ReportCreatedResponse(
        report_id=report.id,
        download_url=download_url,
        expires_at=expires_at,
        report_hash=report_hash,
        file_size=result["file_size"],
    )


@router.get(
    "",
    summary="Listar relatórios do tenant",
    response_model=list[ReportListItem],
)
def list_reports(
    report_type: Optional[str] = Query(default=None, description="'validation' ou 'batch'"),
    job_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Report]:
    """List PDF reports for the authenticated tenant, newest first."""
    from sqlalchemy import select

    stmt = (
        select(Report)
        .where(Report.tenant_id == current_user.tenant_id)
        .order_by(Report.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if report_type:
        stmt = stmt.where(Report.report_type == report_type)
    if job_id:
        stmt = stmt.where(Report.job_id == job_id)

    return list(db.scalars(stmt).all())


@router.get(
    "/{report_id}/download",
    summary="Obter URL de download presigned para um relatório",
    response_model=DownloadResponse,
)
def download_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DownloadResponse:
    """Generate a presigned GET URL (15 min TTL) for a stored PDF report."""
    from sqlalchemy import select

    stmt = select(Report).where(
        Report.id == report_id,
        Report.tenant_id == current_user.tenant_id,
    )
    report = db.scalars(stmt).first()

    if report is None:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")

    if report.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Relatório ainda não está disponível (status={report.status}).",
        )

    try:
        download_url = s3_tool.get_object_url(key=report.storage_key, expires_in=_PRESIGNED_TTL)
    except Exception:
        logger.exception("Erro ao gerar URL presigned para report_id=%s", report_id)
        raise HTTPException(status_code=503, detail="Erro ao gerar URL de download.")

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_PRESIGNED_TTL)
    return DownloadResponse(download_url=download_url, expires_at=expires_at)
