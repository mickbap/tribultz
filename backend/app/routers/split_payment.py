"""Split Payment Dashboard — rastreabilidade de crédito CBS/IBS por NF (LC 214 art. 22).

GET  /api/v1/split-payment/summary          → totais por status (gated: profissional+)
GET  /api/v1/split-payment/status/{doc_id}  → status + crédito de um documento
PATCH /api/v1/split-payment/status/{doc_id} → atualizar status manualmente (fase 1)

Fase 2 (não implementada aqui): Celery beat task que consulta Nota Nacional
(NT 2025.002) para atualizar status automaticamente.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from app.api.deps import get_current_user
from app.api.plan_gate import require_plan
from app.database import get_db
from app.models.auth import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/split-payment", tags=["split-payment"])

VALID_STATUSES = {"pending", "confirmed", "credit_released", "failed"}

# ── Schemas ─────────────────────────────────────────────────────────────────


class SplitPaymentDoc(BaseModel):
    document_id: str
    original_filename: Optional[str]
    doc_type: str
    split_payment_status: str
    credit_value: Optional[str]       # CBS + IBS (R$), from fiscal_metadata
    credit_due_date: Optional[str]    # ISO date, from fiscal_metadata
    created_at: str
    days_pending: Optional[int]       # days since created_at if still pending


class SplitPaymentStatusUpdate(BaseModel):
    status: str
    credit_value: Optional[str] = None    # R$ total CBS+IBS
    credit_due_date: Optional[str] = None  # ISO date (expected confirmation)


class SplitPaymentSummary(BaseModel):
    pending_count: int
    pending_total: str        # R$ sum
    confirmed_count: int
    confirmed_total: str
    credit_released_count: int
    credit_released_total: str
    failed_count: int
    failed_total: str         # crédito em risco
    at_risk_count: int        # pending > 5 dias
    at_risk_total: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_doc(row: Any) -> SplitPaymentDoc:
    fm = row.fiscal_metadata if isinstance(row.fiscal_metadata, dict) else {}
    created_at_str = row.created_at.isoformat() if row.created_at else ""
    days_pending = None
    if row.split_payment_status == "pending" and row.created_at:
        delta = datetime.now(timezone.utc) - row.created_at.replace(tzinfo=timezone.utc)
        days_pending = delta.days
    return SplitPaymentDoc(
        document_id=str(row.id),
        original_filename=row.original_filename,
        doc_type=row.doc_type,
        split_payment_status=row.split_payment_status,
        credit_value=fm.get("credit_value"),
        credit_due_date=fm.get("credit_due_date"),
        created_at=created_at_str,
        days_pending=days_pending,
    )


def _sum_credit(rows: list[Any]) -> str:
    total = 0.0
    for r in rows:
        fm = r.fiscal_metadata if isinstance(r.fiscal_metadata, dict) else {}
        try:
            total += float(fm.get("credit_value") or 0)
        except (ValueError, TypeError):
            pass
    return f"{total:.2f}"


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/summary",
    response_model=SplitPaymentSummary,
    dependencies=[Depends(require_plan("profissional", "empresarial", "contador"))],
)
def split_payment_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SplitPaymentSummary:
    """Aggregate Split Payment credit totals by status for the authenticated tenant."""
    rows = db.execute(
        text("""
            SELECT id, fiscal_metadata, split_payment_status, created_at
            FROM documents
            WHERE tenant_id = :tid
              AND split_payment_status IS NOT NULL
            ORDER BY created_at DESC
        """),
        {"tid": str(current_user.tenant_id)},
    ).fetchall()

    by_status: dict[str, list[Any]] = {s: [] for s in VALID_STATUSES}
    at_risk: list[Any] = []

    for r in rows:
        st = r.split_payment_status
        if st in by_status:
            by_status[st].append(r)
        if st == "pending":
            delta = datetime.now(timezone.utc) - r.created_at.replace(tzinfo=timezone.utc)
            if delta.days > 5:
                at_risk.append(r)

    return SplitPaymentSummary(
        pending_count=len(by_status["pending"]),
        pending_total=_sum_credit(by_status["pending"]),
        confirmed_count=len(by_status["confirmed"]),
        confirmed_total=_sum_credit(by_status["confirmed"]),
        credit_released_count=len(by_status["credit_released"]),
        credit_released_total=_sum_credit(by_status["credit_released"]),
        failed_count=len(by_status["failed"]),
        failed_total=_sum_credit(by_status["failed"]),
        at_risk_count=len(at_risk),
        at_risk_total=_sum_credit(at_risk),
    )


@router.get(
    "/documents",
    response_model=list[SplitPaymentDoc],
    dependencies=[Depends(require_plan("profissional", "empresarial", "contador"))],
)
def list_split_payment_documents(
    status: Optional[str] = Query(None, pattern="^(pending|confirmed|credit_released|failed)$"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SplitPaymentDoc]:
    """List documents tracked for Split Payment, optionally filtered by status."""
    filters = ["tenant_id = :tid", "split_payment_status IS NOT NULL"]
    params: dict[str, Any] = {"tid": str(current_user.tenant_id), "limit": limit}

    if status:
        filters.append("split_payment_status = :status")
        params["status"] = status

    where = " AND ".join(filters)
    rows = db.execute(
        text(f"""
            SELECT id, original_filename, doc_type, fiscal_metadata,
                   split_payment_status, created_at
            FROM documents
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        params,
    ).fetchall()

    return [_to_doc(r) for r in rows]


@router.get(
    "/status/{document_id}",
    response_model=SplitPaymentDoc,
    dependencies=[Depends(require_plan("profissional", "empresarial", "contador"))],
)
def get_split_payment_status(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SplitPaymentDoc:
    """Get Split Payment status for a single document."""
    try:
        row = db.execute(
            text("""
                SELECT id, original_filename, doc_type, fiscal_metadata,
                       split_payment_status, created_at
                FROM documents
                WHERE id = CAST(:id AS uuid) AND tenant_id = :tid
            """),
            {"id": document_id, "tid": str(current_user.tenant_id)},
        ).fetchone()
    except Exception:
        raise HTTPException(404, "Documento não encontrado")
    if not row:
        raise HTTPException(404, "Documento não encontrado")
    if not row.split_payment_status:
        raise HTTPException(400, "Este documento não está rastreado no Split Payment")
    return _to_doc(row)


@router.patch(
    "/status/{document_id}",
    response_model=SplitPaymentDoc,
    dependencies=[Depends(require_plan("profissional", "empresarial", "contador"))],
)
def update_split_payment_status(
    document_id: str,
    body: SplitPaymentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SplitPaymentDoc:
    """Manually update Split Payment status for a document.

    Phase 1: manual updates. Phase 2: automated via Celery + Nota Nacional API.
    """
    if body.status not in VALID_STATUSES:
        raise HTTPException(400, f"Status inválido. Use: {', '.join(sorted(VALID_STATUSES))}")

    try:
        row = db.execute(
            text("""
                SELECT id, original_filename, doc_type, fiscal_metadata,
                       split_payment_status, created_at
                FROM documents
                WHERE id = CAST(:id AS uuid) AND tenant_id = :tid
            """),
            {"id": document_id, "tid": str(current_user.tenant_id)},
        ).fetchone()
    except Exception:
        raise HTTPException(404, "Documento não encontrado")
    if not row:
        raise HTTPException(404, "Documento não encontrado")

    # Merge fiscal_metadata updates
    fm: dict[str, Any] = dict(row.fiscal_metadata) if isinstance(row.fiscal_metadata, dict) else {}
    if body.credit_value is not None:
        fm["credit_value"] = body.credit_value
    if body.credit_due_date is not None:
        fm["credit_due_date"] = body.credit_due_date

    import json
    db.execute(
        text("""
            UPDATE documents
            SET split_payment_status = :status,
                fiscal_metadata = CAST(:fm AS jsonb),
                updated_at = now()
            WHERE id = CAST(:id AS uuid) AND tenant_id = :tid
        """),
        {
            "status": body.status,
            "fm": json.dumps(fm),
            "id": document_id,
            "tid": str(current_user.tenant_id)
        },
    )
    db.commit()

    updated = db.execute(
        text("""
            SELECT id, original_filename, doc_type, fiscal_metadata,
                   split_payment_status, created_at
            FROM documents
            WHERE id = CAST(:id AS uuid) AND tenant_id = :tid
        """),
        {"id": document_id, "tid": str(current_user.tenant_id)},
    ).fetchone()

    if not updated:
        raise HTTPException(500, "Erro ao recarregar documento")
    return _to_doc(updated)
