"""Plan enforcement dependencies — require_plan, check_usage_limit, increment_usage."""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, cast

from fastapi import Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.billing import Plan, Subscription, UsageTracking
from app.models.founding_partner import resolve_effective_license

logger = logging.getLogger(__name__)


def require_plan(*allowed_slugs: str) -> Callable:
    """FastAPI Depends factory — raises 403 if user's plan is not in allowed_slugs."""

    def _check(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        plan = _get_effective_plan(db, current_user)
        slug = cast(str, plan.slug) if plan else None

        if slug not in allowed_slugs:
            plan_names = ", ".join(s.capitalize() for s in allowed_slugs)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Recurso disponível nos planos: {plan_names}. Faça upgrade para continuar.",
                headers={"X-Upgrade-Required": "true"},
            )
        return current_user

    return _check


def check_usage_limit(usage_type: str) -> Callable:
    """FastAPI Depends factory — raises 403 if monthly usage limit is reached.

    usage_type: 'validations' or 'ai_messages'
    """

    def _check(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        plan = _get_effective_plan(db, current_user)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nenhum plano ativo. Faça upgrade para continuar.",
            )

        # Get the limit from plan
        if usage_type == "validations":
            limit = plan.max_validations  # NULL = unlimited
        elif usage_type == "ai_messages":
            limit = plan.max_ai_messages
        else:
            return current_user  # unknown type, skip check

        # NULL means unlimited
        if limit is None:
            return current_user

        # Check current usage
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        usage = db.execute(
            select(UsageTracking).where(
                UsageTracking.user_id == current_user.id,
                UsageTracking.period == period,
            )
        ).scalar_one_or_none()

        current = 0
        if usage:
            if usage_type == "validations":
                current = cast(int, usage.validations_used)
            else:
                current = cast(int, usage.ai_messages_used)

        if current >= cast(int, limit):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Limite mensal de {usage_type.replace('_', ' ')} atingido ({current}/{limit}). Faça upgrade para continuar.",
                headers={"X-Usage-Limit-Reached": "true"},
            )

        return current_user

    return _check


def increment_usage(db: Session, user_id: object, tenant_id: object, usage_type: str) -> None:
    """Atomically increment a usage counter for the current month.

    Call this AFTER a successful validation or AI message.
    """
    period = datetime.now(timezone.utc).strftime("%Y-%m")

    # Try to find existing row
    usage = db.execute(
        select(UsageTracking).where(
            UsageTracking.user_id == user_id,
            UsageTracking.period == period,
        )
    ).scalar_one_or_none()

    if not usage:
        # Create row (race-safe: unique constraint will prevent duplicates)
        usage = UsageTracking(
            tenant_id=tenant_id,
            user_id=user_id,
            period=period,
        )
        db.add(usage)
        db.flush()

    # Atomic increment via SQL UPDATE
    if usage_type == "validations":
        db.execute(
            update(UsageTracking)
            .where(UsageTracking.id == usage.id)
            .values(validations_used=UsageTracking.validations_used + 1)
        )
    elif usage_type == "ai_messages":
        db.execute(
            update(UsageTracking)
            .where(UsageTracking.id == usage.id)
            .values(ai_messages_used=UsageTracking.ai_messages_used + 1)
        )

    db.flush()


def get_plan_slug(db: Session, user: User) -> str | None:
    """Return the effective plan slug for a user (Grant Adapter aware), or None."""
    plan = _get_effective_plan(db, user)
    if plan is None:
        return None
    return str(plan.slug)


def get_effective_plan(db: Session, user: User) -> Any:
    """Public wrapper — resolve o Plan completo (não só o slug) do usuário."""
    return _get_effective_plan(db, user)


def _get_effective_plan(db: Session, user: User) -> Any:
    """Resolve o Plan efetivo do usuário — Grant ativo (ADR-0008, Grant Adapter)
    tem precedência sobre a assinatura, mesmo ponto único de resolução já usado
    no login (`auth.py`: ``resolve_effective_license``). Sem isso, um Early
    Adopter com Grant ativo (sem Subscription — RNF002) nunca passava em
    `require_plan`/`check_usage_limit`/`get_plan_slug`, apesar do JWT reportar
    o plano correto (#487).

    Ator ``partner`` (RFC-0026) não tem ``tenant_id`` — não há Grant possível,
    devolve a assinatura como está (tipicamente None).
    """
    _sub, sub_plan = _get_active_subscription(db, user)
    if user.tenant_id is None:
        return sub_plan
    base_slug = cast(str, sub_plan.slug) if sub_plan is not None else ""
    effective_slug, source = resolve_effective_license(db, cast(Any, user.tenant_id), base_slug)
    if source == "subscription":
        return sub_plan
    return db.execute(select(Plan).where(Plan.slug == effective_slug)).scalar_one_or_none()


def _get_active_subscription(db: Session, user: User) -> tuple[Any, Any]:
    """Get the user's most recent subscription + plan. Returns (sub, plan) or (None, None)."""
    result = db.execute(
        select(Subscription, Plan)
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(
            Subscription.user_id == user.id,
            Subscription.status.in_(("active", "trial", "pending", "cancelled")),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    ).first()

    if not result:
        return (None, None)

    sub, plan = result[0], result[1]

    # Cancelled subs: only grant access if period hasn't ended
    if cast(str, sub.status) == "cancelled":
        if sub.current_period_end is not None:
            period_end = cast(datetime, sub.current_period_end)
            if period_end < datetime.now(timezone.utc):
                return (None, None)
        else:
            return (None, None)

    return (sub, plan)
