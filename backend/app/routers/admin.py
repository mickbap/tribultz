"""Admin dashboard router — superadmin-only metrics aggregation."""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User, Tenant
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
                SELECT DATE(created_at) AS day, COUNT(*) AS count
                FROM users
                WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY DATE(created_at)
                ORDER BY day
            """)
        ).fetchall()
        return [{"day": str(r.day), "count": r.count} for r in rows]
    except Exception:
        return []


def _plan_distribution(db: Session) -> list[dict[str, Any]]:
    """Count subscriptions per plan slug."""
    try:
        rows = db.execute(
            select(Plan.slug, func.count(Subscription.id).label("count"))
            .select_from(Subscription)
            .join(Plan, Subscription.plan_id == Plan.id)
            .group_by(Plan.slug)
        ).fetchall()
        return [{"plan": r.slug, "count": r.count} for r in rows]
    except Exception:
        return []


def _revenue_by_plan(db: Session, month_start: datetime) -> list[dict[str, Any]]:
    """Revenue per plan this month (from confirmed payments)."""
    try:
        rows = db.execute(
            text("""
                SELECT p.slug, COUNT(pay.id) AS count,
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
            {"plan": r.slug, "count": r.count, "total_cents": r.total_cents}
            for r in rows
        ]
    except Exception:
        return []


def _validations_last_7_days(db: Session) -> list[dict[str, Any]]:
    """Daily validation counts for the last 7 days."""
    try:
        rows = db.execute(
            text("""
                SELECT DATE(created_at) AS day, COUNT(*) AS count
                FROM jobs
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(created_at)
                ORDER BY day
            """)
        ).fetchall()
        return [{"day": str(r.day), "count": r.count} for r in rows]
    except Exception:
        return []


def _support_stats(db: Session) -> dict[str, int]:
    """Support ticket counts by status."""
    try:
        rows = db.execute(
            text("""
                SELECT status, COUNT(*) AS count
                FROM support_tickets
                GROUP BY status
            """)
        ).fetchall()
        result: dict[str, int] = {"open": 0, "in_progress": 0, "resolved": 0, "closed": 0}
        for r in rows:
            result[str(r.status)] = int(r.count)
        return result
    except Exception:
        return {"open": 0, "in_progress": 0, "resolved": 0, "closed": 0}


def _feedback_stats(db: Session, month_start: datetime) -> dict[str, int]:
    """Feedback counts by category this month."""
    try:
        rows = db.execute(
            text("""
                SELECT category, COUNT(*) AS count
                FROM feedback
                WHERE created_at >= :start
                GROUP BY category
            """),
            {"start": month_start},
        ).fetchall()
        result: dict[str, int] = {}
        total = 0
        for r in rows:
            result[str(r.category)] = int(r.count)
            total += int(r.count)
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
def admin_dashboard(
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
    redis_data = _redis_info(settings.REDIS_URL)

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
        "validations": {
            "today": validations_today,
            "month": validations_month,
            "total": validations_total,
            "last_7_days": _validations_last_7_days(db),
        },
        "support": _support_stats(db),
        "feedback": _feedback_stats(db, month_start),
    }
