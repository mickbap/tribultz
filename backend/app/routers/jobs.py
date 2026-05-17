"""Orchestration / Job Control Agent — manages async job lifecycle."""

import json
import logging
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, text, update as sa_update
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.api.plan_gate import require_plan, get_plan_slug
from app.models.auth import User
from app.models.jobs import Job
from app.services.fiscal_justification import enrich_findings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


# ── Enums & Schemas ──────────────────────────────────────────────────────────
class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NEEDS_HUMAN = "NEEDS_HUMAN"


class JobCreateRequest(BaseModel):
    # tenant_slug removed - derived from auth
    job_type: str                           # e.g. "validate_batch", "import_nfe"
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None   # for safe retries


class JobUpdateRequest(BaseModel):
    status: JobStatus
    result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    tenant_id: str
    job_type: str
    status: str
    idempotency_key: Optional[str]
    payload: dict[str, Any]
    result: Optional[dict[str, Any]]
    error_message: Optional[str]
    created_at: str
    updated_at: str
    # Findings enriched with justificativa técnica (server-side gate by plan)
    findings: Optional[list[dict[str, Any]]] = None



def _row_to_response(r) -> JobResponse:
    raw_result = r.result if isinstance(r.result, dict) else None
    findings = None
    if raw_result:
        raw_findings = raw_result.get("findings")
        if isinstance(raw_findings, list) and raw_findings:
            findings = raw_findings
    return JobResponse(
        id=str(r.id),
        tenant_id=str(r.tenant_id),
        job_type=r.job_type,
        status=r.status,
        idempotency_key=r.idempotency_key,
        payload=r.payload if isinstance(r.payload, dict) else {},
        result=raw_result,
        error_message=r.error_message,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
        findings=findings,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("", response_model=JobResponse, status_code=201)
def create_job(
    req: JobCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enqueue a new job.  If an idempotency_key is provided and already
    exists for this tenant, the existing job is returned (safe retry).
    """

    tenant_id = str(current_user.tenant_id)

    # Idempotent check
    if req.idempotency_key:
        existing = db.execute(
            text("""
                SELECT * FROM jobs
                WHERE tenant_id = :tid AND idempotency_key = :key
            """),
            {"tid": tenant_id, "key": req.idempotency_key},
        ).fetchone()
        if existing:
            return _row_to_response(existing)

    job_id = str(uuid4())
    db.execute(
        text("""
            INSERT INTO jobs (id, tenant_id, job_type, status,
                              idempotency_key, payload)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :jtype, 'QUEUED', :key, CAST(:payload AS jsonb))
        """),
        {
            "id": job_id,
            "tid": tenant_id,
            "jtype": req.job_type,
            "key": req.idempotency_key,
            "payload": json.dumps(req.payload),
        },
    )
    db.commit()

    row = db.execute(
        text("SELECT * FROM jobs WHERE id = :id AND tenant_id = :tid"),
        {"id": job_id, "tid": tenant_id},
    ).fetchone()
    return _row_to_response(row)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get job status by ID.

    Returns findings enriched with justificativa técnica (base legal + explicação + correção)
    gated by subscription plan:
      - profissional / empresarial / contador → justification included
      - trial / starter → justification_gated=True (frontend shows upgrade CTA)
    """

    tenant_id = str(current_user.tenant_id)
    try:
        row = db.execute(
            text("SELECT * FROM jobs WHERE id = CAST(:id AS uuid) AND tenant_id = :tid"),
            {"id": job_id, "tid": tenant_id},
        ).fetchone()
    except Exception:
        raise HTTPException(404, "Job not found")
    if not row:
        raise HTTPException(404, "Job not found")

    response = _row_to_response(row)

    # Enrich findings with justificativa técnica based on plan
    result = response.result or {}
    raw_findings = result.get("findings", [])
    if isinstance(raw_findings, list) and raw_findings:
        plan_slug = get_plan_slug(db, current_user)
        response.findings = enrich_findings(raw_findings, plan_slug)

    return response


@router.patch("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: str,
    req: JobUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transition a job to a new status.
    Used by the worker or human-in-the-loop to mark progress.
    """
    patch: dict[str, Any] = {"status": req.status.value, "updated_at": func.now()}
    if req.result is not None:
        patch["result"] = req.result
    if req.error_message is not None:
        patch["error_message"] = req.error_message

    row = db.execute(
        sa_update(Job)
        .where(Job.id == UUID(job_id), Job.tenant_id == current_user.tenant_id)
        .values(**patch)
        .returning(Job)
    ).fetchone()
    db.commit()

    if row is None:
        raise HTTPException(404, "Job not found")
    return _row_to_response(row)


@router.get("", response_model=list[JobResponse])
def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List jobs for the authenticated user's tenant, optionally filtered by status."""

    tenant_id = str(current_user.tenant_id)

    filters = ["j.tenant_id = :tid"]
    params: dict[str, Any] = {"tid": tenant_id, "limit": limit}

    if status:
        filters.append("j.status = :status")
        params["status"] = status.value

    where = " AND ".join(filters)
    rows = db.execute(
        text(f"""
            SELECT * FROM jobs j
            WHERE {where}
            ORDER BY j.created_at DESC
            LIMIT :limit
        """),
        params,
    ).fetchall()

    return [_row_to_response(r) for r in rows]


@router.post("/{job_id}/reprocess", response_model=JobResponse)
def reprocess_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reset a FAILED or NEEDS_HUMAN job back to QUEUED for idempotent retry.
    """

    tenant_id = str(current_user.tenant_id)
    row = db.execute(
        text("SELECT * FROM jobs WHERE id = :id AND tenant_id = :tid"),
        {"id": job_id, "tid": tenant_id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    if row.status not in ("FAILED", "NEEDS_HUMAN"):
        raise HTTPException(
            400, f"Can only reprocess FAILED or NEEDS_HUMAN jobs (current: {row.status})"
        )

    db.execute(
        text("UPDATE jobs SET status = 'QUEUED', error_message = NULL, updated_at = now() WHERE id = :id AND tenant_id = :tid"),
        {"id": job_id, "tid": tenant_id},
    )
    db.commit()

    row = db.execute(
        text("SELECT * FROM jobs WHERE id = :id AND tenant_id = :tid"),
        {"id": job_id, "tid": tenant_id},
    ).fetchone()
    return _row_to_response(row)


@router.get("/{job_id}/report.pdf")
def get_job_report_pdf(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _plan: User = Depends(require_plan("profissional", "contador")),
):
    """Generate and return a PDF validation report for a completed job.

    Gated to Profissional and Contador plans.
    """

    tenant_id = str(current_user.tenant_id)

    row = db.execute(
        text("SELECT * FROM jobs WHERE id = :id AND tenant_id = :tid"),
        {"id": job_id, "tid": tenant_id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")

    if row.status != "SUCCESS":
        raise HTTPException(400, f"Job não está completo (status: {row.status})")

    result = row.result if isinstance(row.result, dict) else {}
    payload = row.payload if isinstance(row.payload, dict) else {}
    findings = result.get("findings", [])

    from app.services.pdf_service import generate_validation_report_pdf

    pdf_bytes = generate_validation_report_pdf(
        company_name=payload.get("company_name", ""),
        cnpj=payload.get("cnpj", ""),
        reference_period=payload.get("reference_period", ""),
        job_id=str(row.id),
        findings=findings,
        overall_status=result.get("status", "N/A"),
        total_base=result.get("total_base", "0"),
        total_cbs=result.get("total_cbs", "0"),
        total_ibs=result.get("total_ibs", "0"),
    )

    # Detect if WeasyPrint returned HTML fallback
    content_type = "application/pdf"
    filename = f"relatorio_{job_id}.pdf"
    if pdf_bytes[:15] == b"<!DOCTYPE html>":
        content_type = "text/html; charset=utf-8"
        filename = f"relatorio_{job_id}.html"

    return Response(
        content=pdf_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/{job_id}/export/erp",
    summary="Exportar catálogo de produtos do job em formato ERP (TOTVS, SAP, Omie, Linx, Genérico)",
)
def export_job_erp(
    job_id: str,
    format: str = Query("generic", pattern="^(totvs|sap|omie|linx|generic)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _plan: User = Depends(require_plan("profissional", "empresarial", "contador")),
) -> Response:
    tenant_id = str(current_user.tenant_id)
    row = db.execute(
        text("SELECT * FROM jobs WHERE id = :id AND tenant_id = :tid"),
        {"id": job_id, "tid": tenant_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    if row.status != "SUCCESS":
        raise HTTPException(status_code=400, detail=f"Job não concluído (status: {row.status}).")

    result = row.result if isinstance(row.result, dict) else {}
    produtos = result.get("produtos", [])
    if not produtos:
        raise HTTPException(
            status_code=400,
            detail="Este job não possui catálogo de produtos exportável. Apenas jobs SPED suportam export ERP.",
        )

    from app.services.erp_export import generate as erp_generate

    content, content_type, suffix = erp_generate(produtos, format, result.get("periodo", {}).get("ini"))  # type: ignore[arg-type]
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="tribultz_erp_{job_id[:8]}_{suffix}"'},
    )
