"""Exception requests router — CRUD + notificação por e-mail.

Fluxo:
1. Operador abre exceção em um finding informando justificativa + admin (nome + e-mail)
2. Sistema registra no banco e envia e-mail informativo para o admin
3. Operador (ou outro user do tenant) decide (APPROVED/REJECTED) dentro do app
4. Auditoria via audit_log: exception_created e exception_decided
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.exception_requests import ExceptionRequest
from app.services.email_service import send_exception_notification_email
from app.tools import postgres_tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/exceptions", tags=["exceptions"])


# ── Schemas ───────────────────────────────────────────────────────────────


class ExceptionCreateRequest(BaseModel):
    job_id: Optional[str] = None
    finding_id: str = Field(..., min_length=1)
    rule_id: str = Field(..., min_length=1)
    justification: str = Field(..., min_length=1)
    admin_name: str = Field(..., min_length=1)
    admin_email: EmailStr
    # Mantido por compat com payload legado do frontend; ignorado se enviado.
    created_by: Optional[str] = None


class ExceptionDecisionRequest(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    decision_comment: Optional[str] = None
    # Compat com payload legado; ignorado — usamos current_user.email.
    decided_by: Optional[str] = None


class ExceptionRequestResponse(BaseModel):
    id: str
    tenant_id: str
    job_id: Optional[str] = None
    finding_id: str
    rule_id: str
    justification: str
    status: str
    admin_name: str
    admin_email: str
    created_by: str
    created_at: str
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    decision_comment: Optional[str] = None


def _to_response(row: ExceptionRequest) -> ExceptionRequestResponse:
    return ExceptionRequestResponse(
        id=str(row.id),
        tenant_id=str(row.tenant_id),
        job_id=str(row.job_id) if row.job_id else None,
        finding_id=row.finding_id,
        rule_id=row.rule_id,
        justification=row.justification,
        status=row.status,
        admin_name=row.admin_name,
        admin_email=row.admin_email,
        created_by=row.created_by,
        created_at=row.created_at.isoformat() if row.created_at else "",
        decided_by=row.decided_by,
        decided_at=row.decided_at.isoformat() if row.decided_at else None,
        decision_comment=row.decision_comment,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("", response_model=ExceptionRequestResponse, status_code=201)
def create_exception_request(
    req: ExceptionCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExceptionRequestResponse:
    """Cria uma exceção e dispara e-mail informativo para o admin indicado."""
    job_uuid: Optional[UUID] = None
    if req.job_id:
        try:
            job_uuid = UUID(req.job_id)
        except ValueError:
            # job_id inválido (ex: fingerprint legado) — registra exceção sem vincular
            logger.warning("create_exception: invalid job_id %r — saving without link", req.job_id)
            job_uuid = None

    operator_email = current_user.email
    operator_name = current_user.full_name or operator_email
    operator_phone = current_user.phone

    row = ExceptionRequest(
        id=uuid4(),
        tenant_id=current_user.tenant_id,
        job_id=job_uuid,
        finding_id=req.finding_id,
        rule_id=req.rule_id,
        justification=req.justification,
        status="OPEN",
        admin_name=req.admin_name,
        admin_email=str(req.admin_email),
        created_by=operator_email,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # Audit log (não-bloqueante via try/except)
    try:
        postgres_tool.insert_audit_log(
            tenant_id=str(current_user.tenant_id),
            user_id=str(current_user.id),
            action="exception_created",
            entity_type="exception_request",
            entity_id=str(row.id),
            payload={
                "rule_id": row.rule_id,
                "finding_id": row.finding_id,
                "admin_email": row.admin_email,
            },
        )
    except Exception:
        logger.warning("create_exception: audit_log failed", exc_info=True)

    # Envio de e-mail em background — não bloqueia o response
    background_tasks.add_task(
        send_exception_notification_email,
        to_email=str(req.admin_email),
        admin_name=req.admin_name,
        operator_name=operator_name,
        operator_email=operator_email,
        operator_phone=operator_phone,
    )

    return _to_response(row)


@router.get("", response_model=list[ExceptionRequestResponse])
def list_exception_requests(
    status: Optional[str] = Query(default=None, pattern="^(OPEN|APPROVED|REJECTED)$"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExceptionRequestResponse]:
    """Lista exceções do tenant, com filtro opcional por status."""
    q = (
        db.query(ExceptionRequest)
        .filter(ExceptionRequest.tenant_id == current_user.tenant_id)
    )
    if status:
        q = q.filter(ExceptionRequest.status == status)
    rows = q.order_by(ExceptionRequest.created_at.desc()).limit(limit).all()
    return [_to_response(r) for r in rows]


@router.post("/{exception_id}/decision", response_model=ExceptionRequestResponse)
def decide_exception_request(
    exception_id: str,
    req: ExceptionDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExceptionRequestResponse:
    """Aprova ou rejeita uma exceção. Qualquer user do tenant pode decidir."""
    try:
        ex_uuid = UUID(exception_id)
    except ValueError:
        raise HTTPException(404, "Exception not found")

    row = (
        db.query(ExceptionRequest)
        .filter(
            ExceptionRequest.id == ex_uuid,
            ExceptionRequest.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(404, "Exception not found")
    if row.status != "OPEN":
        raise HTTPException(409, f"Exception already {row.status}")

    row.status = req.status
    row.decided_by = current_user.email
    row.decided_at = datetime.now(timezone.utc)
    row.decision_comment = req.decision_comment
    db.commit()
    db.refresh(row)

    try:
        postgres_tool.insert_audit_log(
            tenant_id=str(current_user.tenant_id),
            user_id=str(current_user.id),
            action="exception_decided",
            entity_type="exception_request",
            entity_id=str(row.id),
            payload={
                "status": row.status,
                "rule_id": row.rule_id,
                "finding_id": row.finding_id,
            },
        )
    except Exception:
        logger.warning("decide_exception: audit_log failed", exc_info=True)

    return _to_response(row)
