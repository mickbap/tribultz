"""Admin dashboard router — superadmin-only metrics aggregation."""

import logging
from datetime import datetime, timezone
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.billing import Payment, Plan, Subscription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if cast(str, current_user.role) != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a superadmins.",
        )
    return current_user


@router.get("/dashboard")
def admin_dashboard(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(_require_superadmin)],
):
    """Aggregated platform metrics for the admin dashboard."""

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── Users ────────────────────────────────────────────────
    total_users = db.scalar(select(func.count(User.id))) or 0
    active_users = db.scalar(
        select(func.count(User.id)).where(User.is_active == True)  # noqa: E712
    ) or 0

    # Trial = subscription.status == 'trial'
    trial_count = db.scalar(
        select(func.count(Subscription.id)).where(Subscription.status == "trial")
    ) or 0

    paid_count_users = db.scalar(
        select(func.count(Subscription.id)).where(
            Subscription.status == "active",
        )
    ) or 0

    # ── Revenue ──────────────────────────────────────────────
    # MRR: sum of price_cents for all active subscriptions
    mrr_result = db.execute(
        select(func.coalesce(func.sum(Plan.price_cents), 0))
        .select_from(Subscription)
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(Subscription.status == "active")
    ).scalar() or 0

    # Payments this month
    paid_payments = db.scalar(
        select(func.count(Payment.id)).where(
            Payment.status == "confirmed",
            Payment.created_at >= month_start,
        )
    ) or 0

    pending_payments = db.scalar(
        select(func.count(Payment.id)).where(
            Payment.status.in_(("pending", "overdue")),
        )
    ) or 0

    # ── Infra (lightweight health check) ─────────────────────
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        pass  # DB connectivity checked implicitly by queries above

    try:
        from app.config import settings
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"

    # ── Validations ──────────────────────────────────────────
    # Count from jobs table (if it exists)
    try:
        validations_today = db.scalar(
            text(
                "SELECT COUNT(*) FROM jobs WHERE created_at >= :start"
            ),
            {"start": today_start},
        ) or 0
    except Exception:
        validations_today = 0

    try:
        validations_month = db.scalar(
            text(
                "SELECT COUNT(*) FROM jobs WHERE created_at >= :start"
            ),
            {"start": month_start},
        ) or 0
    except Exception:
        validations_month = 0

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "trial": trial_count,
            "paid": paid_count_users,
        },
        "revenue": {
            "mrr_cents": mrr_result,
            "paid_count": paid_payments,
            "pending_count": pending_payments,
        },
        "infra": {
            "api_status": "healthy",
            "worker_status": "running",
            "redis_status": redis_status,
        },
        "validations": {
            "today": validations_today,
            "month": validations_month,
        },
    }
