"""Command Center — Founding Partners (RFC-0017 + ADR-0008).

Administração operacional do programa Early Adopters pelo Owner (superadmin):
admitir empresa, provisionar acesso, conceder/revogar Grant, encerrar. Toda
mutação é auditada. **Guardrails:** nunca cria/altera Subscription; ASAAS segue
sendo a única origem de assinaturas pagas; o Grant é autorização excepcional.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.database import get_db
from app.models.auth import Tenant, User, UserTenant
from app.models.billing import UsageTracking
from app.models.founding_partner import (
    DEFAULT_GRANT_PLAN,
    EA_ORIGINS,
    EarlyAdopter,
    EarlyGrant,
    effective_grant_status,
)
from app.routers.admin import _audit, _require_superadmin
from app.routers.auth import _cnpj_to_slug

router = APIRouter(prefix="/api/v1/admin/founding-partners", tags=["founding-partners"])


# ── Helpers ──────────────────────────────────────────────────────────────────


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _day_end(d: date) -> datetime:
    return datetime.combine(d, time.max, tzinfo=timezone.utc)


def _grant_out(g: EarlyGrant) -> dict[str, Any]:
    return {
        "id": str(g.id),
        "plan_slug": cast(str, g.plan_slug),
        "starts_at": cast(datetime, g.starts_at).isoformat(),
        "ends_at": cast(datetime, g.ends_at).isoformat(),
        "status": effective_grant_status(g),
        "raw_status": cast(str, g.status),
        "granted_by_email": g.granted_by_email,
        "reason": g.reason,
        "revoked_at": cast(datetime, g.revoked_at).isoformat() if g.revoked_at is not None else None,
        "created_at": cast(datetime, g.created_at).isoformat(),
    }


def _ea_out(db: Session, ea: EarlyAdopter, grants: list[EarlyGrant]) -> dict[str, Any]:
    mine = [g for g in grants if str(g.early_adopter_id) == str(ea.id)]
    active = next((g for g in mine if effective_grant_status(g) == "active"), None)
    return {
        "id": str(ea.id),
        "tenant_id": str(ea.tenant_id),
        "empresa": cast(str, ea.empresa),
        "cnpj": ea.cnpj,
        "email": cast(str, ea.email),
        "responsavel": ea.responsavel,
        "telefone": ea.telefone,
        "origem": cast(str, ea.origem),
        "status": cast(str, ea.status),
        "observacoes": ea.observacoes,
        "created_at": cast(datetime, ea.created_at).isoformat(),
        # Licença efetiva resolvida (o que o Grant Adapter entregaria no login).
        "effective_plan": cast(str, active.plan_slug) if active is not None else None,
        "grant_ends_at": cast(datetime, active.ends_at).isoformat() if active is not None else None,
        "active_grant_id": str(active.id) if active is not None else None,
        "grants": [_grant_out(g) for g in mine],
    }


def _revoke(db: Session, grant: EarlyGrant) -> None:
    grant.status = "revoked"  # type: ignore[assignment]
    grant.revoked_at = datetime.now(timezone.utc)  # type: ignore[assignment]


# ── Bodies ───────────────────────────────────────────────────────────────────


class GrantBody(BaseModel):
    plan_slug: str = DEFAULT_GRANT_PLAN
    starts_on: date
    ends_on: date
    reason: str | None = None


class EarlyAdopterCreate(BaseModel):
    empresa: str
    email: str
    cnpj: str | None = None
    responsavel: str | None = None
    telefone: str | None = None
    origem: str = "outro"
    observacoes: str | None = None
    # Senha inicial do 1º acesso (o Founding Partner troca depois). Login imediato.
    initial_password: str
    # Vigência opcional: se presente, já emite o primeiro Grant no cadastro.
    grant: GrantBody | None = None


class EarlyAdopterUpdate(BaseModel):
    empresa: str | None = None
    responsavel: str | None = None
    telefone: str | None = None
    origem: str | None = None
    observacoes: str | None = None


# ── Provisionamento ──────────────────────────────────────────────────────────


def _provision_tenant_and_user(
    db: Session, data: EarlyAdopterCreate
) -> Tenant:
    """Cria/reusa o Tenant e o usuário de login do Founding Partner.

    Nunca cria Subscription (guardrail RNF002). Se o e-mail já existe, reusa o
    usuário e seu tenant — não duplica identidade.
    """
    existing_user = db.execute(
        select(User).where(User.email == data.email)
    ).scalar_one_or_none()
    if existing_user is not None:
        tenant = db.get(Tenant, existing_user.tenant_id)
        if tenant is None:  # defensivo
            raise HTTPException(status_code=500, detail="Tenant do usuário não encontrado.")
        return tenant

    # Tenant por CNPJ (reusa slug canônico) ou slug derivado.
    if data.cnpj:
        slug = _cnpj_to_slug(data.cnpj)
        tenant = db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name=data.empresa, slug=slug)
            db.add(tenant)
            db.flush()
    else:
        tenant = Tenant(name=data.empresa, slug=f"ea-{uuid.uuid4().hex[:12]}")
        db.add(tenant)
        db.flush()

    user = User(
        tenant_id=tenant.id,
        email=data.email,
        full_name=data.responsavel or data.empresa,
        password_hash=get_password_hash(data.initial_password),
        cnpj=data.cnpj or None,
        phone=data.telefone or None,
        account_type="contador",
        role="contador",
        lgpd_consent_at=datetime.now(timezone.utc),
        email_verified=True,  # 1º acesso via credencial definida pelo Owner
    )
    db.add(user)
    db.flush()
    db.add(UserTenant(user_id=user.id, tenant_id=tenant.id, role="contador", is_default=True))
    db.add(UsageTracking(tenant_id=tenant.id, user_id=user.id, period=datetime.now(timezone.utc).strftime("%Y-%m")))
    return tenant


def _issue_grant(
    db: Session, ea: EarlyAdopter, body: GrantBody, actor_email: str
) -> EarlyGrant:
    if body.ends_on < body.starts_on:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Término não pode ser antes do início.")
    # Um Grant efetivo por vez: revoga os ativos antes de emitir o novo.
    for g in db.execute(
        select(EarlyGrant).where(EarlyGrant.early_adopter_id == ea.id, EarlyGrant.status == "active")
    ).scalars().all():
        _revoke(db, g)
    grant = EarlyGrant(
        early_adopter_id=ea.id,
        tenant_id=ea.tenant_id,
        plan_slug=(body.plan_slug or DEFAULT_GRANT_PLAN),
        starts_at=_day_start(body.starts_on),
        ends_at=_day_end(body.ends_on),
        status="active",
        granted_by_email=actor_email,
        reason=body.reason,
    )
    db.add(grant)
    db.flush()
    return grant


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("")
def list_founding_partners(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
    q: str | None = None,
    status_filter: str | None = None,
) -> dict[str, Any]:
    stmt = select(EarlyAdopter)
    if q:
        stmt = stmt.where(EarlyAdopter.empresa.ilike(f"%{q}%") | EarlyAdopter.email.ilike(f"%{q}%"))
    if status_filter in ("active", "closed"):
        stmt = stmt.where(EarlyAdopter.status == status_filter)
    eas = db.execute(stmt.order_by(EarlyAdopter.created_at.desc())).scalars().all()
    ids = [ea.id for ea in eas]
    grants = (
        db.execute(select(EarlyGrant).where(EarlyGrant.early_adopter_id.in_(ids))).scalars().all()
        if ids
        else []
    )
    return {"total": len(eas), "items": [_ea_out(db, ea, list(grants)) for ea in eas]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_founding_partner(
    body: EarlyAdopterCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    if not body.empresa.strip() or not body.email.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empresa e e-mail são obrigatórios.")
    if len(body.initial_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha inicial deve ter no mínimo 8 caracteres.")
    origem = body.origem.lower().strip()
    if origem not in EA_ORIGINS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Origem inválida: {body.origem}.")

    tenant = _provision_tenant_and_user(db, body)
    ea = EarlyAdopter(
        tenant_id=tenant.id,
        empresa=body.empresa.strip(),
        cnpj=(body.cnpj or None),
        email=body.email.strip(),
        responsavel=(body.responsavel or None),
        telefone=(body.telefone or None),
        origem=origem,
        observacoes=(body.observacoes or None),
    )
    db.add(ea)
    db.flush()
    _audit(db, _admin, "early_adopter.create", "early_adopter", ea.id, {"empresa": ea.empresa, "email": ea.email, "origem": origem})

    grants: list[EarlyGrant] = []
    if body.grant is not None:
        g = _issue_grant(db, ea, body.grant, cast(str, _admin.email))
        _audit(db, _admin, "early_grant.create", "early_grant", g.id, {"early_adopter_id": str(ea.id), "plan_slug": g.plan_slug, "ends_at": g.ends_at.isoformat()})
        grants = [g]

    db.commit()
    db.refresh(ea)
    for g in grants:
        db.refresh(g)
    return _ea_out(db, ea, grants)


@router.patch("/{ea_id}")
def update_founding_partner(
    ea_id: UUID,
    body: EarlyAdopterUpdate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    ea = db.get(EarlyAdopter, ea_id)
    if ea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Early Adopter não encontrado.")
    changed: dict[str, Any] = {}
    if body.origem is not None:
        origem = body.origem.lower().strip()
        if origem not in EA_ORIGINS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Origem inválida: {body.origem}.")
        ea.origem = origem  # type: ignore[assignment]
        changed["origem"] = origem
    for field in ("empresa", "responsavel", "telefone", "observacoes"):
        val = getattr(body, field)
        if val is not None:
            setattr(ea, field, val or None)
            changed[field] = val or None
    _audit(db, _admin, "early_adopter.update", "early_adopter", ea.id, {"changed": changed})
    db.commit()
    grants = db.execute(select(EarlyGrant).where(EarlyGrant.early_adopter_id == ea.id)).scalars().all()
    db.refresh(ea)
    return _ea_out(db, ea, list(grants))


@router.post("/{ea_id}/grants", status_code=status.HTTP_201_CREATED)
def issue_grant(
    ea_id: UUID,
    body: GrantBody,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    ea = db.get(EarlyAdopter, ea_id)
    if ea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Early Adopter não encontrado.")
    if cast(str, ea.status) != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Early Adopter encerrado não pode receber concessão.")
    g = _issue_grant(db, ea, body, cast(str, _admin.email))
    _audit(db, _admin, "early_grant.create", "early_grant", g.id, {"early_adopter_id": str(ea.id), "plan_slug": g.plan_slug, "starts_at": g.starts_at.isoformat(), "ends_at": g.ends_at.isoformat()})
    db.commit()
    db.refresh(g)
    return _grant_out(g)


@router.post("/grants/{grant_id}/revoke")
def revoke_grant(
    grant_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    grant = db.get(EarlyGrant, grant_id)
    if grant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant não encontrado.")
    if cast(str, grant.status) != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Grant já não está ativo.")
    _revoke(db, grant)
    _audit(db, _admin, "early_grant.revoke", "early_grant", grant.id, {"early_adopter_id": str(grant.early_adopter_id)})
    db.commit()
    db.refresh(grant)
    return _grant_out(grant)


@router.post("/{ea_id}/close")
def close_founding_partner(
    ea_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    """Encerra o programa para a empresa: revoga Grants ativos e marca como
    closed — preservando histórico, dados e auditoria (RF005)."""
    ea = db.get(EarlyAdopter, ea_id)
    if ea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Early Adopter não encontrado.")
    revoked = 0
    for g in db.execute(
        select(EarlyGrant).where(EarlyGrant.early_adopter_id == ea.id, EarlyGrant.status == "active")
    ).scalars().all():
        _revoke(db, g)
        revoked += 1
    ea.status = "closed"  # type: ignore[assignment]
    _audit(db, _admin, "early_adopter.close", "early_adopter", ea.id, {"grants_revogados": revoked})
    db.commit()
    grants = db.execute(select(EarlyGrant).where(EarlyGrant.early_adopter_id == ea.id)).scalars().all()
    db.refresh(ea)
    return _ea_out(db, ea, list(grants))
