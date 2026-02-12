"""Orchestration / Job Control Agent – manages async job lifecycle."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


# ── Enums & Schemas ──────────────────────────────────────────
class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NEEDS_HUMAN = "NEEDS_HUMAN"


class JobCreateRequest(BaseModel):
    tenant_slug: str = "default"
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


# ── Bootstrap (ensure jobs table exists) ─────────────────────
_JOBS_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_type        VARCHAR(100) NOT NULL,
    status          VARCHAR(30)  NOT NULL DEFAULT 'QUEUED',
    idempotency_key VARCHAR(200),
    payload         JSONB NOT NULL DEFAULT '{}',
    result          JSONB,
    error_message   TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(tenant_id, status);
"""


def _ensure_table(db: Session):
    db.execute(text(_JOBS_DDL))
    db.commit()


def _get_tenant_id(db: Session, slug: str) -> str:
    row = db.execute(
        text("SELECT id FROM tenants WHERE slug = :slug"), {"slug": slug}
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Tenant '{slug}' not found")
    return str(row.id)


def _row_to_response(r) -> JobResponse:
    return JobResponse(
        id=str(r.id),
        tenant_id=str(r.tenant_id),
        job_type=r.job_type,
        status=r.status,
        idempotency_key=r.idempotency_key,
        payload=r.payload if isinstance(r.payload, dict) else {},
        result=r.result if isinstance(r.result, dict) else None,
        error_message=r.error_message,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


# ── Endpoints ─────────────────────────────────────────────────
@router.post("", response_model=JobResponse, status_code=201)
def create_job(req: JobCreateRequest, db: Session = Depends(get_db)):
    """
    Enqueue a new job.  If an idempotency_key is provided and already
    exists for this tenant, the existing job is returned (safe retry).
    """
    _ensure_table(db)
    tenant_id = _get_tenant_id(db, req.tenant_slug)

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

    import json
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
        text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}
    ).fetchone()
    return _row_to_response(row)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get job status by ID."""
    _ensure_table(db)
    row = db.execute(
        text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}
    ).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    return _row_to_response(row)


@router.patch("/{job_id}", response_model=JobResponse)
def update_job(job_id: str, req: JobUpdateRequest, db: Session = Depends(get_db)):
    """
    Transition a job to a new status.
    Used by the worker or human-in-the-loop to mark progress.
    """
    _ensure_table(db)
    import json

    updates = ["status = :status", "updated_at = now()"]
    params: dict[str, Any] = {"id": job_id, "status": req.status.value}

    if req.result is not None:
        updates.append("result = CAST(:result AS jsonb)")
        params["result"] = json.dumps(req.result)
    if req.error_message is not None:
        updates.append("error_message = :err")
        params["err"] = req.error_message

    set_clause = ", ".join(updates)
    db.execute(text(f"UPDATE jobs SET {set_clause} WHERE id = :id"), params)
    db.commit()

    row = db.execute(
        text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}
    ).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    return _row_to_response(row)


@router.get("", response_model=list[JobResponse])
def list_jobs(
    tenant_slug: str = "default",
    status: Optional[JobStatus] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List jobs for a tenant, optionally filtered by status."""
    _ensure_table(db)
    tenant_id = _get_tenant_id(db, tenant_slug)

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
def reprocess_job(job_id: str, db: Session = Depends(get_db)):
    """
    Reset a FAILED or NEEDS_HUMAN job back to QUEUED for idempotent retry.
    """
    _ensure_table(db)
    row = db.execute(
        text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}
    ).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    if row.status not in ("FAILED", "NEEDS_HUMAN"):
        raise HTTPException(
            400, f"Can only reprocess FAILED or NEEDS_HUMAN jobs (current: {row.status})"
        )

    db.execute(
        text("UPDATE jobs SET status = 'QUEUED', error_message = NULL, updated_at = now() WHERE id = :id"),
        {"id": job_id},
    )
    db.commit()

    row = db.execute(
        text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}
    ).fetchone()
    return _row_to_response(row)
