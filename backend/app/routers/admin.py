"""Admin dashboard router — superadmin-only metrics aggregation."""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import get_password_hash
from app.database import get_db
from app.models.admin_audit import AdminAuditLog
from app.models.api_key import ApiKey
from app.models.auth import User, Tenant
from app.models.billing import Payment, Plan, Subscription
from app.models.partner import (
    PARTNER_STATUSES,
    PARTNER_TYPES,
    Partner,
    normalize_partner_code,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if cast(str, current_user.role) != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a superadmins.",
        )
    return current_user


# ── Helpers ──────────────────────────────────────────────────────────


def _safe_count(db: Session, query: Any) -> int:
    try:
        return db.scalar(query) or 0
    except Exception:
        return 0


def _registrations_last_30_days(db: Session) -> list[dict[str, Any]]:
    """Daily registration counts for the last 30 days."""
    try:
        rows = db.execute(
            text("""
                SELECT DATE(created_at) AS day, COUNT(*) AS cnt
                FROM users
                WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY DATE(created_at)
                ORDER BY day
            """)
        ).fetchall()
        return [{"day": str(r.day), "count": r.cnt} for r in rows]
    except Exception:
        return []


def _plan_distribution(db: Session) -> list[dict[str, Any]]:
    """Count subscriptions per plan slug."""
    try:
        rows = db.execute(
            select(Plan.slug, func.count(Subscription.id).label("cnt"))
            .select_from(Subscription)
            .join(Plan, Subscription.plan_id == Plan.id)
            .group_by(Plan.slug)
        ).fetchall()
        return [{"plan": r.slug, "count": r.cnt} for r in rows]
    except Exception:
        return []


def _active_plan_distribution(db: Session) -> list[dict[str, Any]]:
    """Assinantes ATIVOS por plano (Escopo 5.2, go-live billing) — distinto de
    _plan_distribution, que conta todo status (trial/cancelled inclusive)."""
    try:
        rows = db.execute(
            select(Plan.slug, func.count(Subscription.id).label("cnt"))
            .select_from(Subscription)
            .join(Plan, Subscription.plan_id == Plan.id)
            .where(Subscription.status == "active")
            .group_by(Plan.slug)
        ).fetchall()
        return [{"plan": r.slug, "count": r.cnt} for r in rows]
    except Exception:
        return []


def _churn_rate_month(db: Session, month_start: datetime, active_count: int) -> tuple[int, float]:
    """Churn do mês (Escopo 5.2): cancelamentos no mês / (ativos + cancelados
    no mês) — aproxima a taxa mensal sem precisar de snapshot histórico do
    tamanho da base no início do mês. Retorna (cancelled_month, rate_pct)."""
    cancelled_month = _safe_count(
        db,
        select(func.count(Subscription.id)).where(
            Subscription.cancelled_at.isnot(None),
            Subscription.cancelled_at >= month_start,
        ),
    )
    denominator = active_count + cancelled_month
    rate = round(cancelled_month / denominator * 100, 2) if denominator > 0 else 0.0
    return cancelled_month, rate


def _revenue_by_plan(db: Session, month_start: datetime) -> list[dict[str, Any]]:
    """Revenue per plan this month (from confirmed payments)."""
    try:
        rows = db.execute(
            text("""
                SELECT p.slug, COUNT(pay.id) AS cnt,
                       COALESCE(SUM(pay.amount_cents), 0) AS total_cents
                FROM payments pay
                JOIN subscriptions s ON pay.subscription_id = s.id
                JOIN plans p ON s.plan_id = p.id
                WHERE pay.status = 'confirmed'
                  AND pay.created_at >= :start
                GROUP BY p.slug
                ORDER BY total_cents DESC
            """),
            {"start": month_start},
        ).fetchall()
        return [
            {"plan": r.slug, "count": r.cnt, "total_cents": r.total_cents}
            for r in rows
        ]
    except Exception:
        return []


def _validations_last_7_days(db: Session) -> list[dict[str, Any]]:
    """Daily validation counts for the last 7 days."""
    try:
        rows = db.execute(
            text("""
                SELECT DATE(created_at) AS day, COUNT(*) AS cnt
                FROM jobs
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(created_at)
                ORDER BY day
            """)
        ).fetchall()
        return [{"day": str(r.day), "count": r.cnt} for r in rows]
    except Exception:
        return []


def _support_stats(db: Session) -> dict[str, int]:
    """Support ticket counts by status."""
    try:
        rows = db.execute(
            text("""
                SELECT status, COUNT(*) AS cnt
                FROM support_tickets
                GROUP BY status
            """)
        ).fetchall()
        result: dict[str, int] = {"open": 0, "in_progress": 0, "resolved": 0, "closed": 0}
        for r in rows:
            result[str(r.status)] = int(r.cnt)
        return result
    except Exception:
        return {"open": 0, "in_progress": 0, "resolved": 0, "closed": 0}


def _feedback_stats(db: Session, month_start: datetime) -> dict[str, int]:
    """Feedback counts by category this month."""
    try:
        rows = db.execute(
            text("""
                SELECT category, COUNT(*) AS cnt
                FROM feedback
                WHERE created_at >= :start
                GROUP BY category
            """),
            {"start": month_start},
        ).fetchall()
        result: dict[str, int] = {}
        total = 0
        for r in rows:
            result[str(r.category)] = int(r.cnt)
            total += int(r.cnt)
        result["total"] = total
        return result
    except Exception:
        return {"total": 0}


def _redis_info(redis_url: str) -> dict[str, Any]:
    """Get Redis memory and connection info."""
    try:
        import redis as redis_lib
        r = redis_lib.from_url(redis_url, socket_connect_timeout=2)
        r.ping()
        info: dict[str, Any] = r.info(section="memory")  # type: ignore[assignment]
        clients: dict[str, Any] = r.info(section="clients")  # type: ignore[assignment]
        server: dict[str, Any] = r.info(section="server")  # type: ignore[assignment]
        return {
            "status": "healthy",
            "used_memory_human": info.get("used_memory_human", "?"),
            "connected_clients": clients.get("connected_clients", 0),
            "uptime_days": server.get("uptime_in_days", 0),
        }
    except Exception:
        return {"status": "unhealthy", "used_memory_human": "?", "connected_clients": 0, "uptime_days": 0}


# ── Main endpoint ────────────────────────────────────────────────────


@router.get("/dashboard")
async def admin_dashboard(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
):
    """Aggregated platform metrics for the admin dashboard (Phase 1 MVP)."""

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── Users ────────────────────────────────────────────────
    total_users = _safe_count(db, select(func.count(User.id)))
    active_users = _safe_count(
        db, select(func.count(User.id)).where(User.is_active == True)  # noqa: E712
    )
    trial_count = _safe_count(
        db, select(func.count(Subscription.id)).where(Subscription.status == "trial")
    )
    paid_count = _safe_count(
        db, select(func.count(Subscription.id)).where(Subscription.status == "active")
    )
    cancelled_count = _safe_count(
        db, select(func.count(Subscription.id)).where(Subscription.status == "cancelled")
    )
    total_tenants = _safe_count(db, select(func.count(Tenant.id)))

    cancelled_month, churn_rate_month = _churn_rate_month(db, month_start, paid_count)

    registrations_today = _safe_count(
        db, select(func.count(User.id)).where(User.created_at >= today_start)
    )

    # ── Revenue ──────────────────────────────────────────────
    mrr_cents = db.execute(
        select(func.coalesce(func.sum(Plan.price_cents), 0))
        .select_from(Subscription)
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(Subscription.status == "active")
    ).scalar() or 0

    total_revenue_cents = _safe_count(
        db,
        select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
            Payment.status == "confirmed"
        ),
    )
    revenue_month_cents = _safe_count(
        db,
        select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
            Payment.status == "confirmed",
            Payment.created_at >= month_start,
        ),
    )

    paid_payments_month = _safe_count(
        db,
        select(func.count(Payment.id)).where(
            Payment.status == "confirmed",
            Payment.created_at >= month_start,
        ),
    )
    pending_payments = _safe_count(
        db, select(func.count(Payment.id)).where(Payment.status == "pending")
    )
    overdue_payments = _safe_count(
        db, select(func.count(Payment.id)).where(Payment.status == "overdue")
    )

    # ── Infra ────────────────────────────────────────────────
    from app.config import settings
    from app.services.cloudflare_analytics import get_today_traffic
    redis_data = _redis_info(settings.REDIS_URL)
    site_traffic = await get_today_traffic()

    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    # ── Validations ──────────────────────────────────────────
    try:
        validations_today = db.scalar(
            text("SELECT COUNT(*) FROM jobs WHERE created_at >= :start"),
            {"start": today_start},
        ) or 0
    except Exception:
        validations_today = 0

    try:
        validations_month = db.scalar(
            text("SELECT COUNT(*) FROM jobs WHERE created_at >= :start"),
            {"start": month_start},
        ) or 0
    except Exception:
        validations_month = 0

    try:
        validations_total = db.scalar(text("SELECT COUNT(*) FROM jobs")) or 0
    except Exception:
        validations_total = 0

    # ── Aggregated response ──────────────────────────────────
    return {
        "generated_at": now.isoformat(),
        "users": {
            "total": total_users,
            "active": active_users,
            "trial": trial_count,
            "paid": paid_count,
            "cancelled": cancelled_count,
            "tenants": total_tenants,
            "registrations_today": registrations_today,
            "registrations_30d": _registrations_last_30_days(db),
            "plan_distribution": _plan_distribution(db),
            "active_plan_distribution": _active_plan_distribution(db),
            "churn_rate_month_pct": churn_rate_month,
            "cancelled_month": cancelled_month,
        },
        "revenue": {
            "mrr_cents": mrr_cents,
            "total_revenue_cents": total_revenue_cents,
            "revenue_month_cents": revenue_month_cents,
            "paid_count_month": paid_payments_month,
            "pending_count": pending_payments,
            "overdue_count": overdue_payments,
            "by_plan": _revenue_by_plan(db, month_start),
        },
        "infra": {
            "api_status": "healthy",
            "db_status": db_status,
            "redis": redis_data,
        },
        "site_traffic": site_traffic,
        "validations": {
            "today": validations_today,
            "month": validations_month,
            "total": validations_total,
            "last_7_days": _validations_last_7_days(db),
        },
        "support": _support_stats(db),
        "feedback": _feedback_stats(db, month_start),
    }


# ── Drill-down (leitura) — visão top-down completa (superadmin) ──────────────

@router.get("/me")
def admin_me(_admin: Annotated[User, Depends(_require_superadmin)]) -> dict[str, Any]:
    """Ping de autorização: 200 só para superadmin (usado pelo guard do layout /admin)."""
    return {"email": cast(str, _admin.email), "role": cast(str, _admin.role), "is_superadmin": True}


@router.get("/tenants")
def admin_tenants(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
    limit: int = 50,
    offset: int = 0,
    q: str | None = None,
    partner_id: UUID | None = None,
) -> dict[str, Any]:
    stmt = select(Tenant)
    if q:
        stmt = stmt.where(Tenant.name.ilike(f"%{q}%"))
    if partner_id is not None:
        stmt = stmt.where(Tenant.partner_id == partner_id)
    total = _safe_count(db, select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        stmt.order_by(Tenant.created_at.desc()).limit(min(limit, 200)).offset(max(offset, 0))
    ).scalars().all()
    # Proveniência comercial (RFC-0025): resolve os Partners referenciados em lote.
    partner_ids = {t.partner_id for t in rows if t.partner_id is not None}
    partners = {
        p.id: p
        for p in (
            db.execute(select(Partner).where(Partner.id.in_(partner_ids))).scalars().all()
            if partner_ids
            else []
        )
    }
    items = []
    for t in rows:
        p = partners.get(t.partner_id) if t.partner_id is not None else None
        items.append(
            {
                "id": str(t.id),
                "name": cast(str, t.name),
                "is_active": bool(t.is_active),
                "users": _safe_count(db, select(func.count(User.id)).where(User.tenant_id == t.id)),
                "created_at": cast(datetime, t.created_at).isoformat(),
                "partner_id": str(t.partner_id) if t.partner_id is not None else None,
                "partner_name": cast(str, p.name) if p is not None else None,
                "partner_code": cast(str, p.code) if p is not None else None,
            }
        )
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/users")
def admin_users(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
    limit: int = 50,
    offset: int = 0,
    q: str | None = None,
) -> dict[str, Any]:
    stmt = select(User)
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q}%") | User.full_name.ilike(f"%{q}%"))
    total = _safe_count(db, select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        stmt.order_by(User.created_at.desc()).limit(min(limit, 200)).offset(max(offset, 0))
    ).scalars().all()
    items = [
        {
            "id": str(u.id),
            "email": cast(str, u.email),
            "full_name": cast(str, u.full_name),
            "role": cast(str, u.role),
            "is_active": bool(u.is_active),
            "created_at": cast(datetime, u.created_at).isoformat(),
        }
        for u in rows
    ]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/usage")
def admin_usage(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def _jobs_since(start: datetime | None) -> int:
        try:
            if start is None:
                return db.scalar(text("SELECT COUNT(*) FROM jobs")) or 0
            return db.scalar(text("SELECT COUNT(*) FROM jobs WHERE created_at >= :s"), {"s": start}) or 0
        except Exception:
            return 0

    credits = db.execute(
        select(func.coalesce(func.sum(ApiKey.credits_balance), 0)).where(ApiKey.is_active == True)  # noqa: E712
    ).scalar() or 0

    return {
        "generated_at": now.isoformat(),
        "jobs": {"today": _jobs_since(today_start), "month": _jobs_since(month_start), "total": _jobs_since(None)},
        "api_keys": {
            "total": _safe_count(db, select(func.count(ApiKey.id))),
            "active": _safe_count(db, select(func.count(ApiKey.id)).where(ApiKey.is_active == True)),  # noqa: E712
            "credits_balance": int(credits),
            "used_today": _safe_count(db, select(func.count(ApiKey.id)).where(ApiKey.last_used_at >= today_start)),
        },
    }


# ── Fase 2 — ações administrativas (auditadas) + audit log (superadmin) ──────

def _audit(
    db: Session, actor: User, action: str, target_type: str, target_id: Any, detail: dict[str, Any]
) -> None:
    """Registra a ação na trilha de auditoria (mesma transação da mutação)."""
    db.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            actor_email=cast(str, actor.email),
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            detail=detail,
        )
    )


class SetActiveBody(BaseModel):
    is_active: bool


@router.post("/users/{user_id}/active")
def admin_set_user_active(
    user_id: UUID,
    body: SetActiveBody,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    if str(user.id) == str(_admin.id) and not body.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Você não pode desativar a si mesmo.")
    before = bool(user.is_active)
    user.is_active = body.is_active  # type: ignore[assignment]
    _audit(
        db, _admin,
        "user.activate" if body.is_active else "user.deactivate",
        "user", user.id,
        {"before": before, "after": body.is_active, "email": cast(str, user.email)},
    )
    db.commit()
    return {"id": str(user.id), "is_active": body.is_active}


@router.post("/tenants/{tenant_id}/active")
def admin_set_tenant_active(
    tenant_id: UUID,
    body: SetActiveBody,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado.")
    before = bool(tenant.is_active)
    tenant.is_active = body.is_active  # type: ignore[assignment]
    _audit(
        db, _admin,
        "tenant.activate" if body.is_active else "tenant.deactivate",
        "tenant", tenant.id,
        {"before": before, "after": body.is_active, "name": cast(str, tenant.name)},
    )
    db.commit()
    return {"id": str(tenant.id), "is_active": body.is_active}


@router.get("/audit-log")
def admin_audit_log_list(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    total = _safe_count(db, select(func.count(AdminAuditLog.id)))
    rows = db.execute(
        select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(min(limit, 200)).offset(max(offset, 0))
    ).scalars().all()
    items = [
        {
            "id": str(r.id),
            "actor_email": cast(str, r.actor_email),
            "action": cast(str, r.action),
            "target_type": cast(str, r.target_type),
            "target_id": r.target_id,
            "detail": r.detail,
            "created_at": cast(datetime, r.created_at).isoformat(),
        }
        for r in rows
    ]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


# ── Partner Attribution — proveniência comercial (RFC-0025, superadmin) ───────
#
# Partner = EXCLUSIVAMENTE origem comercial. Nunca comissão/contrato/financeiro.
# Sem exclusão física: desativação via status. Toda mutação é auditada.


def _partner_out(db: Session, p: Partner) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "type": cast(str, p.type),
        "name": cast(str, p.name),
        "company": p.company,
        "email": p.email,
        "phone": p.phone,
        "code": cast(str, p.code),
        "status": cast(str, p.status),
        "notes": p.notes,
        "companies": _safe_count(db, select(func.count(Tenant.id)).where(Tenant.partner_id == p.id)),
        # Cadastro operacional (RFC-0026, ADR-0011) — se já tem conta de login.
        "has_account": db.execute(select(User.id).where(User.partner_id == p.id)).scalar_one_or_none() is not None,
        "created_at": cast(datetime, p.created_at).isoformat(),
        "updated_at": cast(datetime, p.updated_at).isoformat(),
    }


class PartnerCreateBody(BaseModel):
    type: str = "other"
    name: str
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    code: str
    notes: str | None = None


class PartnerUpdateBody(BaseModel):
    type: str | None = None
    name: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    code: str | None = None
    notes: str | None = None


class SetPartnerBody(BaseModel):
    # partner_id = None desvincula a origem (raro; auditado).
    partner_id: UUID | None = None


class PartnerAccountCreateBody(BaseModel):
    email: EmailStr
    full_name: str
    initial_password: str


def _validate_code_unique(db: Session, raw: str, exclude_id: UUID | None = None) -> str:
    code = normalize_partner_code(raw)
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido. Use A-Z, 0-9, _ ou -, 3 a 32 caracteres.",
        )
    stmt = select(Partner).where(Partner.code == code)
    if exclude_id is not None:
        stmt = stmt.where(Partner.id != exclude_id)
    if db.execute(stmt).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um Partner com o código {code}.",
        )
    return code


@router.get("/partners")
def admin_partners(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
    limit: int = 50,
    offset: int = 0,
    q: str | None = None,
    status_filter: str | None = None,
) -> dict[str, Any]:
    stmt = select(Partner)
    if q:
        stmt = stmt.where(Partner.name.ilike(f"%{q}%") | Partner.code.ilike(f"%{q}%"))
    if status_filter in PARTNER_STATUSES:
        stmt = stmt.where(Partner.status == status_filter)
    total = _safe_count(db, select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        stmt.order_by(Partner.created_at.desc()).limit(min(limit, 200)).offset(max(offset, 0))
    ).scalars().all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_partner_out(db, p) for p in rows],
    }


@router.post("/partners", status_code=status.HTTP_201_CREATED)
def admin_create_partner(
    body: PartnerCreateBody,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    ptype = body.type.lower().strip()
    if ptype not in PARTNER_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Tipo inválido: {body.type}.")
    if not body.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome é obrigatório.")
    code = _validate_code_unique(db, body.code)
    partner = Partner(
        type=ptype,
        name=body.name.strip(),
        company=(body.company or None),
        email=(body.email or None),
        phone=(body.phone or None),
        code=code,
        notes=(body.notes or None),
    )
    db.add(partner)
    db.flush()
    _audit(db, _admin, "partner.create", "partner", partner.id, {"code": code, "name": partner.name, "type": ptype})
    db.commit()
    db.refresh(partner)
    return _partner_out(db, partner)


@router.patch("/partners/{partner_id}")
def admin_update_partner(
    partner_id: UUID,
    body: PartnerUpdateBody,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner não encontrado.")
    changed: dict[str, Any] = {}
    if body.type is not None:
        ptype = body.type.lower().strip()
        if ptype not in PARTNER_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Tipo inválido: {body.type}.")
        partner.type = ptype  # type: ignore[assignment]
        changed["type"] = ptype
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome é obrigatório.")
        partner.name = body.name.strip()  # type: ignore[assignment]
        changed["name"] = partner.name
    if body.code is not None:
        code = _validate_code_unique(db, body.code, exclude_id=partner_id)
        partner.code = code  # type: ignore[assignment]
        changed["code"] = code
    for field in ("company", "email", "phone", "notes"):
        val = getattr(body, field)
        if val is not None:
            setattr(partner, field, val or None)
            changed[field] = val or None
    _audit(db, _admin, "partner.update", "partner", partner.id, {"changed": changed})
    db.commit()
    db.refresh(partner)
    return _partner_out(db, partner)


@router.post("/partners/{partner_id}/active")
def admin_set_partner_active(
    partner_id: UUID,
    body: SetActiveBody,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner não encontrado.")
    new_status = "active" if body.is_active else "inactive"
    before = cast(str, partner.status)
    partner.status = new_status  # type: ignore[assignment]
    _audit(
        db, _admin,
        "partner.activate" if body.is_active else "partner.deactivate",
        "partner", partner.id,
        {"before": before, "after": new_status, "code": cast(str, partner.code)},
    )
    db.commit()
    return {"id": str(partner.id), "status": new_status}


@router.post("/partners/{partner_id}/account", status_code=status.HTTP_201_CREATED)
def admin_create_partner_account(
    partner_id: UUID,
    body: PartnerAccountCreateBody,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    """Cria a conta de login do Partner (RFC-0026, ADR-0011 — Programa de Parceiros, Fase 1).

    Mesmo padrão do Founding Partner (_provision_tenant_and_user): admin
    provisiona com senha inicial — sem convite/e-mail automático (não existe
    hoje no código). ``User.partner_id`` é setado, ``tenant_id`` fica NULL —
    o CHECK constraint do banco (migration 2026_07_16_0027) garante que essa
    separação nunca é violada. Um Partner tem no máximo uma conta nesta fase.
    """
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner não encontrado.")
    if cast(str, partner.status) != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Partner inativo não pode receber conta.")
    if len(body.initial_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha inicial deve ter no mínimo 8 caracteres.")
    if not body.full_name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome é obrigatório.")

    existing_account = db.execute(
        select(User).where(User.partner_id == partner.id)
    ).scalar_one_or_none()
    if existing_account is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este Partner já possui uma conta.")

    # Login busca por e-mail globalmente (scalar_one_or_none) — e-mail precisa
    # ser único entre TODOS os atores, não só entre partners.
    if db.execute(select(User).where(User.email == body.email)).scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este e-mail já está em uso.")

    user = User(
        partner_id=partner.id,
        email=body.email,
        full_name=body.full_name.strip(),
        password_hash=get_password_hash(body.initial_password),
        role="partner",
        email_verified=True,
    )
    db.add(user)
    db.flush()
    _audit(db, _admin, "partner.create_account", "partner", partner.id, {"user_id": str(user.id), "email": body.email})
    db.commit()
    db.refresh(user)
    return {"user_id": str(user.id), "partner_id": str(partner.id), "email": cast(str, user.email)}


@router.post("/tenants/{tenant_id}/partner")
def admin_set_tenant_partner(
    tenant_id: UUID,
    body: SetPartnerBody,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
) -> dict[str, Any]:
    """Atribui/ajusta manualmente a origem de uma empresa (casos vindos do
    Microsoft Forms + criação manual — RFC-0025)."""
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado.")
    before = str(tenant.partner_id) if tenant.partner_id is not None else None
    if body.partner_id is not None:
        partner = db.get(Partner, body.partner_id)
        if partner is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner não encontrado.")
        if cast(str, partner.status) != "active":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Partner inativo não pode ser vinculado.")
    tenant.partner_id = body.partner_id  # type: ignore[assignment]
    _audit(
        db, _admin, "tenant.set_partner", "tenant", tenant.id,
        {"before": before, "after": str(body.partner_id) if body.partner_id else None},
    )
    db.commit()
    return {"id": str(tenant.id), "partner_id": str(body.partner_id) if body.partner_id else None}
