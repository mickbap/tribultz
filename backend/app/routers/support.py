"""Support router — tickets, feedback enhancement, known errors + GitHub Issues."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.feedback import Feedback
from app.models.support import KnownError, SupportMessage, SupportTicket
from app.services.email_service import (
    send_feedback_received_email,
    send_staff_ticket_notification,
    send_support_ticket_email,
    send_ticket_status_email,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/support", tags=["support"])

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = "mickbap/tribultz"

# ── Schemas ────────────────────────────────────────────────────────────────────


class TicketCreate(BaseModel):
    title: str
    description: str
    priority: Literal["low", "medium", "high", "critical"] = "medium"

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Título deve ter no mínimo 5 caracteres.")
        if len(v) > 200:
            raise ValueError("Título deve ter no máximo 200 caracteres.")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 20:
            raise ValueError("Descrição deve ter no mínimo 20 caracteres.")
        if len(v) > 5000:
            raise ValueError("Descrição deve ter no máximo 5000 caracteres.")
        return v


class TicketRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    user_id: UUID
    title: str
    description: str
    status: str
    priority: str
    attachments: list
    github_issue_url: Optional[str]
    created_at: datetime
    updated_at: datetime


class TicketStatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved", "closed"]


class MessageCreate(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Mensagem não pode ser vazia.")
        if len(v) > 5000:
            raise ValueError("Mensagem deve ter no máximo 5000 caracteres.")
        return v


class MessageRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    ticket_id: UUID
    user_id: Optional[UUID]
    is_staff: bool
    body: str
    created_at: datetime


class FeedbackCreateV2(BaseModel):
    category: Literal["bug", "sugestao", "elogio", "feature"]
    title: str
    message: str
    rating: Optional[int] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Título deve ter no mínimo 3 caracteres.")
        return v[:200]

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Mensagem deve ter no mínimo 10 caracteres.")
        if len(v) > 2000:
            raise ValueError("Mensagem deve ter no máximo 2000 caracteres.")
        return v

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 5):
            raise ValueError("Rating deve ser entre 1 e 5.")
        return v


class FeedbackRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    user_id: UUID
    category: str
    message: str
    created_at: datetime


class KnownErrorCreate(BaseModel):
    code: str
    title: str
    description: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    workaround: Optional[str] = None
    affected_versions: Optional[str] = None


class KnownErrorRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    code: str
    title: str
    description: str
    severity: str
    workaround: Optional[str]
    github_issue_number: Optional[int]
    github_issue_url: Optional[str]
    affected_versions: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime


# ── Ticket endpoints ───────────────────────────────────────────────────────────


@router.post("/tickets", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: TicketCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    ticket = SupportTicket(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        title=data.title,
        description=data.description,
        priority=data.priority,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    # Auto-emails (best-effort)
    try:
        send_support_ticket_email(
            to_email=str(current_user.email),
            user_name=str(current_user.full_name) or str(current_user.email),
            ticket_title=data.title,
            priority=data.priority,
        )
        send_staff_ticket_notification(
            ticket_title=data.title,
            user_email=str(current_user.email),
            priority=data.priority,
        )
    except Exception:
        logger.exception("support_ticket_email_failed ticket_id=%s", ticket.id)

    logger.info("support_ticket_created id=%s user=%s", ticket.id, current_user.id)
    return ticket


@router.get("/tickets", response_model=list[TicketRead])
def list_tickets(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    stmt = (
        select(SupportTicket)
        .where(SupportTicket.tenant_id == current_user.tenant_id)
        .order_by(SupportTicket.created_at.desc())
        .limit(100)
    )
    return db.execute(stmt).scalars().all()


@router.get("/tickets/{ticket_id}", response_model=TicketRead)
def get_ticket(
    ticket_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Ticket não encontrado.")
    return ticket


@router.post("/tickets/{ticket_id}/messages", response_model=MessageRead, status_code=201)
def add_message(
    ticket_id: UUID,
    data: MessageCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Ticket não encontrado.")

    is_staff = str(getattr(current_user, "role", "")) in ("superadmin", "admin")
    msg = SupportMessage(
        ticket_id=ticket_id,
        user_id=current_user.id,
        is_staff=is_staff,
        body=data.body,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.get("/tickets/{ticket_id}/messages", response_model=list[MessageRead])
def list_messages(
    ticket_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Ticket não encontrado.")

    stmt = (
        select(SupportMessage)
        .where(SupportMessage.ticket_id == ticket_id)
        .order_by(SupportMessage.created_at.asc())
    )
    return db.execute(stmt).scalars().all()


@router.patch("/tickets/{ticket_id}/status", response_model=TicketRead)
def update_ticket_status(
    ticket_id: UUID,
    data: TicketStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    role = str(getattr(current_user, "role", ""))
    if role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito à equipe Tribultz.")

    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket não encontrado.")

    old_status = ticket.status
    ticket.status = data.status  # type: ignore[assignment]
    ticket.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    db.commit()
    db.refresh(ticket)

    if old_status != data.status:
        # Fetch ticket owner email for notification
        owner = db.get(User, ticket.user_id)
        if owner:
            try:
                send_ticket_status_email(
                    to_email=str(owner.email),
                    user_name=str(owner.full_name) or str(owner.email),
                    ticket_title=str(ticket.title),
                    new_status=data.status,
                )
            except Exception:
                logger.exception("ticket_status_email_failed ticket=%s", ticket_id)

    return ticket


# ── Feedback endpoints ─────────────────────────────────────────────────────────


@router.post("/feedback", response_model=FeedbackRead, status_code=201)
def create_feedback(
    data: FeedbackCreateV2,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    feedback = Feedback(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        category=data.category,
        message=f"{data.title}: {data.message}",
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    try:
        send_feedback_received_email(
            to_email=str(current_user.email),
            user_name=str(current_user.full_name) or str(current_user.email),
        )
    except Exception:
        logger.exception("feedback_email_failed user=%s", current_user.id)

    return feedback


@router.get("/feedback", response_model=list[FeedbackRead])
def list_feedback(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    role = str(getattr(current_user, "role", ""))
    if role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito.")

    stmt = select(Feedback).order_by(Feedback.created_at.desc()).limit(200)
    return db.execute(stmt).scalars().all()


# ── Known Errors (error catalog) ───────────────────────────────────────────────


@router.get("/errors", response_model=list[KnownErrorRead])
def list_errors(db: Annotated[Session, Depends(get_db)]):
    """Public — list known errors (no auth required)."""
    stmt = select(KnownError).order_by(KnownError.created_at.desc()).limit(100)
    return db.execute(stmt).scalars().all()


@router.post("/errors", response_model=KnownErrorRead, status_code=201)
def create_error(
    data: KnownErrorCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    role = str(getattr(current_user, "role", ""))
    if role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito à equipe Tribultz.")

    existing = db.execute(select(KnownError).where(KnownError.code == data.code)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Código '{data.code}' já existe.")

    error = KnownError(
        code=data.code,
        title=data.title,
        description=data.description,
        severity=data.severity,
        workaround=data.workaround,
        affected_versions=data.affected_versions,
    )
    db.add(error)
    db.commit()
    db.refresh(error)
    return error


@router.post("/errors/{error_id}/github-issue", response_model=KnownErrorRead)
def create_github_issue(
    error_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a GitHub Issue for this known error and link it back."""
    role = str(getattr(current_user, "role", ""))
    if role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito.")

    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN não configurado.")

    error = db.get(KnownError, error_id)
    if error is None:
        raise HTTPException(status_code=404, detail="Erro não encontrado.")

    if error.github_issue_url:
        raise HTTPException(status_code=409, detail="GitHub Issue já criada.")

    severity_label_map = {
        "low": "priority: low",
        "medium": "priority: medium",
        "high": "priority: high",
        "critical": "priority: critical",
    }
    severity = str(error.severity)
    body = (
        f"## {error.title}\n\n"
        f"**Código:** `{error.code}`\n"
        f"**Severidade:** {severity.capitalize()}\n"
        f"**Versões afetadas:** {error.affected_versions or 'não especificado'}\n\n"
        f"### Descrição\n\n{error.description}\n\n"
        + (f"### Contorno\n\n{error.workaround}\n\n" if error.workaround else "")
        + "_Criado automaticamente pelo catálogo de erros Tribultz._"
    )

    resp = httpx.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "title": f"[{error.code}] {error.title}",
            "body": body,
            "labels": ["bug", severity_label_map.get(severity, "bug")],
        },
        timeout=10.0,
    )
    if resp.status_code not in (200, 201):
        logger.error("github_issue_create_failed status=%s body=%s", resp.status_code, resp.text[:300])
        raise HTTPException(status_code=502, detail="Falha ao criar issue no GitHub.")

    issue_data = resp.json()
    error.github_issue_number = issue_data["number"]  # type: ignore[assignment]
    error.github_issue_url = issue_data["html_url"]  # type: ignore[assignment]
    error.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    db.commit()
    db.refresh(error)

    logger.info("github_issue_created error=%s issue=%s", error.code, issue_data["number"])
    return error
