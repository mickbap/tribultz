"""Command Center — Founding Partners (RFC-0017 + ADR-0008).

Administração operacional do programa Early Adopters pelo Owner (superadmin):
admitir empresa, provisionar acesso, conceder/revogar Grant, encerrar. Toda
mutação é auditada. **Guardrails:** nunca cria/altera Subscription; ASAAS segue
sendo a única origem de assinaturas pagas; o Grant é autorização excepcional.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timezone
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.database import get_db
from app.models.auth import Tenant, User, UserTenant
from app.models.billing import Payment, Plan, Subscription, UsageTracking
from app.models.founding_partner import (
    CONVERSION_INTERESSE,
    DEFAULT_GRANT_PLAN,
    EA_ORIGINS,
    EVIDENCE_TYPES,
    JOURNEY_STAGES,
    RECOGNITION_LEVELS,
    TERA_STATUSES,
    CustomerEvidence,
    EarlyAdopter,
    EarlyAdopterJourneyEvent,
    EarlyAdopterTera,
    EarlyGrant,
    effective_grant_status,
)
from app.models.jobs import Job as JobModel
from app.routers.admin import _audit, _require_superadmin
from app.routers.auth import _cnpj_to_slug
from app.services.asaas_service import asaas
from app.tools import s3_tool

logger = logging.getLogger(__name__)

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
        "telefone": ea.telefone,  # exibido como "WhatsApp" na Tela 02
        "cargo": ea.cargo,
        "cidade": ea.cidade,
        "uf": ea.uf,
        "erp": ea.erp,
        "qtd_cnpjs": ea.qtd_cnpjs,
        "volume_nfe_mensal_aprox": ea.volume_nfe_mensal_aprox,
        "origem": cast(str, ea.origem),
        "status": cast(str, ea.status),
        "observacoes": ea.observacoes,
        "proxima_acao": ea.proxima_acao,
        "owner_email": ea.owner_email,
        "recognition": cast(str, ea.recognition),
        "conversion": {
            "interesse": ea.conversion_interesse,
            "motivo": ea.conversion_motivo,
            "plano_slug": ea.conversion_plano_slug,
            "data": cast(datetime, ea.conversion_data).isoformat() if ea.conversion_data is not None else None,
            "valor_cents": ea.conversion_valor_cents,
            "origem": ea.conversion_origem,
        },
        "created_at": cast(datetime, ea.created_at).isoformat(),
        "updated_at": cast(datetime, ea.updated_at).isoformat(),
        # Licença efetiva resolvida (o que o Grant Adapter entregaria no login).
        "effective_plan": cast(str, active.plan_slug) if active is not None else None,
        "grant_ends_at": cast(datetime, active.ends_at).isoformat() if active is not None else None,
        "active_grant_id": str(active.id) if active is not None else None,
        "grants": [_grant_out(g) for g in mine],
    }


def _journey_out(e: EarlyAdopterJourneyEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "stage": cast(str, e.stage),
        "occurred_at": cast(datetime, e.occurred_at).isoformat(),
        "note": e.note,
        "source": "manual",
        "created_by_email": e.created_by_email,
    }


def _evidence_out(ev: CustomerEvidence) -> dict[str, Any]:
    return {
        "id": str(ev.id),
        "tipo": cast(str, ev.tipo),
        "texto": cast(str, ev.texto),
        "autor": ev.autor,
        "occurred_at": cast(datetime, ev.occurred_at).isoformat(),
        "created_at": cast(datetime, ev.created_at).isoformat(),
    }


def _tera_out(t: EarlyAdopterTera) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "versao": cast(str, t.versao),
        "status": cast(str, t.status),
        "responsavel": t.responsavel,
        "has_file": t.storage_key is not None,
        "pdf_link": t.pdf_link,
        "created_at": cast(datetime, t.created_at).isoformat(),
    }


def _auto_journey_events(db: Session, ea: EarlyAdopter) -> list[dict[str, Any]]:
    """Eventos derivados AO VIVO do próprio sistema — nunca gravados (RFC-0024,
    princípio "observar, não replicar"): 1º login (users.first_login_at) e XML
    recebido (1º job de validate_xml do tenant)."""
    events: list[dict[str, Any]] = []
    user = db.execute(select(User).where(User.email == ea.email)).scalar_one_or_none()
    if user is not None and user.first_login_at is not None:
        events.append({
            "id": None, "stage": "primeiro_login",
            "occurred_at": cast(datetime, user.first_login_at).isoformat(),
            "note": None, "source": "auto", "created_by_email": None,
        })
    xml_count = db.scalar(
        select(func.count(JobModel.id)).where(JobModel.tenant_id == ea.tenant_id, JobModel.job_type == "validate_xml")
    ) or 0
    if xml_count > 0:
        first_job = db.execute(
            select(JobModel)
            .where(JobModel.tenant_id == ea.tenant_id, JobModel.job_type == "validate_xml")
            .order_by(JobModel.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()
        if first_job is not None:
            events.append({
                "id": None, "stage": "xml_recebido",
                "occurred_at": cast(datetime, first_job.created_at).isoformat(),
                "note": f"{xml_count} validação(ões) até agora", "source": "auto", "created_by_email": None,
            })
    return events


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
    cargo: str | None = None
    cidade: str | None = None
    uf: str | None = None
    erp: str | None = None
    qtd_cnpjs: int | None = None
    volume_nfe_mensal_aprox: int | None = None
    proxima_acao: str | None = None
    owner_email: str | None = None
    recognition: str | None = None


class JourneyEventCreate(BaseModel):
    stage: str
    occurred_at: datetime | None = None
    note: str | None = None


class EvidenceCreate(BaseModel):
    tipo: str
    texto: str
    occurred_at: datetime | None = None
    autor: str | None = None


class ConversionInterestBody(BaseModel):
    interesse: str
    motivo: str | None = None


class ConversionBody(BaseModel):
    plan_slug: str
    billing_type: str = "PIX"
    motivo: str | None = None
    origem: str | None = None


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
    if body.recognition is not None:
        recognition = body.recognition.lower().strip()
        if recognition not in RECOGNITION_LEVELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Reconhecimento inválido: {body.recognition}.")
        ea.recognition = recognition  # type: ignore[assignment]
        changed["recognition"] = recognition
    for field in (
        "empresa", "responsavel", "telefone", "observacoes", "cargo", "cidade", "uf",
        "erp", "qtd_cnpjs", "volume_nfe_mensal_aprox", "proxima_acao", "owner_email",
    ):
        val = getattr(body, field)
        if val is not None:
            setattr(ea, field, val if val != "" else None)
            changed[field] = val if val != "" else None
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


# ── Tela 02 — Perfil do participante (RFC-0024) ─────────────────────────────


@router.get("/{ea_id}")
def get_founding_partner(
    ea_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    """Perfil completo (Tela 02): cadastrais, jornada (manual + derivada ao vivo),
    Customer Evidence, TERA e o snapshot do sistema que alimenta a jornada."""
    ea = db.get(EarlyAdopter, ea_id)
    if ea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Early Adopter não encontrado.")
    grants = db.execute(select(EarlyGrant).where(EarlyGrant.early_adopter_id == ea.id)).scalars().all()
    manual_events = db.execute(
        select(EarlyAdopterJourneyEvent).where(EarlyAdopterJourneyEvent.early_adopter_id == ea.id)
    ).scalars().all()
    evidences = db.execute(
        select(CustomerEvidence).where(CustomerEvidence.early_adopter_id == ea.id).order_by(CustomerEvidence.occurred_at.desc())
    ).scalars().all()
    teras = db.execute(
        select(EarlyAdopterTera).where(EarlyAdopterTera.early_adopter_id == ea.id).order_by(EarlyAdopterTera.created_at.desc())
    ).scalars().all()
    user = db.execute(select(User).where(User.email == ea.email)).scalar_one_or_none()

    journey = [_journey_out(e) for e in manual_events] + _auto_journey_events(db, ea)
    journey.sort(key=lambda x: cast(str, x["occurred_at"]))

    out = _ea_out(db, ea, list(grants))
    out["journey"] = journey
    out["customer_evidence"] = [_evidence_out(e) for e in evidences]
    out["tera"] = [_tera_out(t) for t in teras]
    out["system"] = {
        "user_id": str(user.id) if user is not None else None,
        "first_login_at": cast(datetime, user.first_login_at).isoformat() if user is not None and user.first_login_at is not None else None,
        "last_login_at": cast(datetime, user.last_login_at).isoformat() if user is not None and user.last_login_at is not None else None,
    }
    return out


@router.post("/{ea_id}/journey", status_code=status.HTTP_201_CREATED)
def add_journey_event(
    ea_id: UUID,
    body: JourneyEventCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    """Lança um evento de jornada manual. Eventos automáticos (1º login, XML
    recebido) NUNCA passam por aqui — são derivados ao vivo em `GET /{ea_id}`."""
    ea = db.get(EarlyAdopter, ea_id)
    if ea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Early Adopter não encontrado.")
    stage = body.stage.strip()
    if stage not in JOURNEY_STAGES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Etapa de jornada inválida: {stage}.")
    event = EarlyAdopterJourneyEvent(
        early_adopter_id=ea.id,
        stage=stage,
        occurred_at=body.occurred_at or datetime.now(timezone.utc),
        note=(body.note or None),
        created_by_email=cast(str, _admin.email),
    )
    db.add(event)
    db.flush()
    _audit(db, _admin, "early_adopter.journey_event", "early_adopter", ea.id, {"stage": stage})
    db.commit()
    db.refresh(event)
    return _journey_out(event)


@router.post("/{ea_id}/evidence", status_code=status.HTTP_201_CREATED)
def add_customer_evidence(
    ea_id: UUID,
    body: EvidenceCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    """Registra Customer Evidence (RFC-0019/ADR-0005: Discovery, nunca Knowledge
    — não altera o Brain automaticamente; é só a superfície de captura)."""
    ea = db.get(EarlyAdopter, ea_id)
    if ea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Early Adopter não encontrado.")
    tipo = body.tipo.strip()
    if tipo not in EVIDENCE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Tipo de evidência inválido: {tipo}.")
    if not body.texto.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Texto é obrigatório.")
    ev = CustomerEvidence(
        early_adopter_id=ea.id,
        tipo=tipo,
        texto=body.texto.strip(),
        autor=(body.autor or cast(str, _admin.email)),
        occurred_at=body.occurred_at or datetime.now(timezone.utc),
    )
    db.add(ev)
    db.flush()
    _audit(db, _admin, "early_adopter.evidence_create", "early_adopter", ea.id, {"tipo": tipo})
    db.commit()
    db.refresh(ev)
    return _evidence_out(ev)


@router.post("/{ea_id}/tera", status_code=status.HTTP_201_CREATED)
async def add_tera(
    ea_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
    versao: str = Form(...),
    tera_status: str = Form("rascunho"),
    responsavel: str | None = Form(None),
    pdf_link: str | None = Form(None),
    file: UploadFile | None = File(None),
) -> dict[str, Any]:
    """Registro MANUAL do TERA (v1, RFC-0024): upload de PDF e/ou link externo.
    A geração automática de TERA depende do RFC-0018, ainda não construído."""
    ea = db.get(EarlyAdopter, ea_id)
    if ea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Early Adopter não encontrado.")
    if not versao.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Versão é obrigatória.")
    if tera_status not in TERA_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Status de TERA inválido: {tera_status}.")

    storage_key: str | None = None
    if file is not None:
        raw = await file.read()
        storage_key = f"documents/{ea.tenant_id}/tera/{uuid.uuid4()}.pdf"
        s3_tool.put_object(
            key=storage_key, data=raw, content_type="application/pdf",
            metadata={"artifact_kind": "tera", "early_adopter_id": str(ea.id)},
        )

    tera = EarlyAdopterTera(
        early_adopter_id=ea.id,
        versao=versao.strip(),
        status=tera_status,
        responsavel=(responsavel or None),
        storage_key=storage_key,
        pdf_link=(pdf_link or None),
    )
    db.add(tera)
    db.flush()
    _audit(db, _admin, "early_adopter.tera_create", "early_adopter", ea.id, {"versao": versao, "status": tera_status})
    db.commit()
    db.refresh(tera)
    return _tera_out(tera)


@router.get("/tera/{tera_id}/download")
def download_tera(
    tera_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    tera = db.get(EarlyAdopterTera, tera_id)
    if tera is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TERA não encontrado.")
    if tera.storage_key is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este TERA não tem PDF enviado (só link).")
    return {"download_url": s3_tool.get_object_url(cast(str, tera.storage_key))}


@router.patch("/{ea_id}/conversion")
def update_conversion_interest(
    ea_id: UUID,
    body: ConversionInterestBody,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    """Registra o interesse em continuar (Sim/Não/Pensando) sem iniciar ASAAS —
    esse gatilho é exclusivo de `POST /{ea_id}/convert` ("Gerar assinatura ASAAS")."""
    ea = db.get(EarlyAdopter, ea_id)
    if ea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Early Adopter não encontrado.")
    interesse = body.interesse.strip().lower()
    if interesse not in CONVERSION_INTERESSE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Interesse inválido: {interesse}.")
    ea.conversion_interesse = interesse  # type: ignore[assignment]
    ea.conversion_motivo = (body.motivo or None)  # type: ignore[assignment]
    _audit(db, _admin, "early_adopter.conversion_interest", "early_adopter", ea.id, {"interesse": interesse})
    db.commit()
    grants = db.execute(select(EarlyGrant).where(EarlyGrant.early_adopter_id == ea.id)).scalars().all()
    db.refresh(ea)
    return _ea_out(db, ea, list(grants))


@router.post("/{ea_id}/convert")
async def convert_founding_partner(
    ea_id: UUID,
    body: ConversionBody,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    """Inicia a conversão em cliente pagante — reusa o fluxo ASAAS (mesmas
    chamadas de `billing.py:upgrade_plan`: `asaas.create_customer` /
    `asaas.create_subscription`). **Proibido gateway paralelo** (RFC-0024).

    Não é literalmente `upgrade_plan`: um Early Adopter tipicamente não tem
    NENHUMA Subscription prévia (Grant nunca cria Subscription — RNF002), então
    `upgrade_plan` (que exige uma assinatura existente para substituir) não se
    aplica aqui. Esta função cobre o caso "sem assinatura anterior"; se por
    algum motivo já existir uma, ela é cancelada como no upgrade normal.
    """
    ea = db.get(EarlyAdopter, ea_id)
    if ea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Early Adopter não encontrado.")

    target_plan = db.execute(
        select(Plan).where(Plan.slug == body.plan_slug, Plan.is_active == True)  # noqa: E712
    ).scalar_one_or_none()
    if target_plan is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plano não encontrado.")
    if cast(int, target_plan.price_cents) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conversão exige um plano pago.")

    user = db.execute(select(User).where(User.email == ea.email)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário de login do Early Adopter não encontrado.")

    existing_sub = db.execute(
        select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.desc()).limit(1)
    ).scalar_one_or_none()
    customer_id = (
        cast(str, existing_sub.asaas_customer_id)
        if existing_sub is not None and existing_sub.asaas_customer_id is not None
        else None
    )
    cnpj_value = cast(str, user.cnpj).strip() if user.cnpj is not None else ""
    if not customer_id and len(cnpj_value.replace(".", "").replace("/", "").replace("-", "")) not in (11, 14):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Early Adopter sem CNPJ válido cadastrado — atualize antes de converter.")

    if existing_sub is not None and cast(str, existing_sub.status) in ("active", "trial", "pending"):
        old_asaas_id = cast(str, existing_sub.asaas_subscription_id) if existing_sub.asaas_subscription_id is not None else None
        if old_asaas_id:
            try:
                await asaas.cancel_subscription(old_asaas_id)
            except Exception:
                logger.warning("Falha ao cancelar assinatura Asaas anterior na conversão: %s", old_asaas_id)
        existing_sub.status = "cancelled"  # type: ignore[assignment]
        existing_sub.cancelled_at = datetime.now(timezone.utc)  # type: ignore[assignment]

    value = cast(int, target_plan.price_cents) / 100.0
    checkout_url = None
    pix_qr_code = None
    pix_copy_paste = None
    try:
        if not customer_id:
            cust = await asaas.create_customer(
                name=cast(str, user.full_name), email=cast(str, user.email),
                cpf_cnpj=cnpj_value, phone=cast(str, user.phone) if user.phone is not None else "",
            )
            customer_id = cust["id"]
        sub_resp = await asaas.create_subscription(
            customer_id=customer_id, value=value, billing_type=body.billing_type.upper(),
            description=f"Conversão Founding Partner — {cast(str, target_plan.name)}",
        )
        new_asaas_sub_id = sub_resp["id"]
        sub_payments = await asaas.get_subscription_payments(new_asaas_sub_id)
        if not sub_payments:
            raise ValueError("Assinatura Asaas criada sem pagamento associado")
        first_payment = sub_payments[0]
        asaas_payment_id = first_payment["id"]
        if body.billing_type.upper() == "PIX":
            pix_data = await asaas.get_pix_qr_code(asaas_payment_id)
            pix_qr_code = pix_data.get("encodedImage")
            pix_copy_paste = pix_data.get("payload")
        else:
            checkout_url = asaas.get_checkout_url(asaas_payment_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Erro ao criar assinatura Asaas na conversão do Founding Partner")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Erro ao iniciar a assinatura. Tente novamente.")

    new_sub = Subscription(
        tenant_id=ea.tenant_id, user_id=user.id, plan_id=target_plan.id, status="pending",
        asaas_customer_id=customer_id, asaas_subscription_id=new_asaas_sub_id,
    )
    db.add(new_sub)
    db.flush()
    db.add(Payment(
        tenant_id=ea.tenant_id, subscription_id=new_sub.id, asaas_payment_id=asaas_payment_id,
        amount_cents=cast(int, target_plan.price_cents), status="pending",
        payment_method=body.billing_type.lower(), pix_qr_code=pix_qr_code, pix_copy_paste=pix_copy_paste,
    ))

    ea.conversion_interesse = "sim"  # type: ignore[assignment]
    ea.conversion_motivo = (body.motivo or ea.conversion_motivo)  # type: ignore[assignment]
    ea.conversion_plano_slug = cast(str, target_plan.slug)  # type: ignore[assignment]
    ea.conversion_data = datetime.now(timezone.utc)  # type: ignore[assignment]
    ea.conversion_valor_cents = cast(int, target_plan.price_cents)  # type: ignore[assignment]
    ea.conversion_origem = (body.origem or ea.conversion_origem)  # type: ignore[assignment]
    _audit(db, _admin, "early_adopter.convert", "early_adopter", ea.id, {"plan_slug": target_plan.slug, "subscription_id": str(new_sub.id)})
    db.commit()
    db.refresh(ea)
    grants = db.execute(select(EarlyGrant).where(EarlyGrant.early_adopter_id == ea.id)).scalars().all()
    return {
        "early_adopter": _ea_out(db, ea, list(grants)),
        "subscription_id": str(new_sub.id),
        "checkout_url": checkout_url,
        "pix_qr_code": pix_qr_code,
        "pix_copy_paste": pix_copy_paste,
    }
