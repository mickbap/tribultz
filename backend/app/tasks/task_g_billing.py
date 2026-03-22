"""Celery tasks for billing lifecycle — trial expiry and monthly usage reset."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.celery_app import celery
from app.database import SessionLocal
from app.models.auth import User
from app.models.billing import Subscription, UsageTracking

logger = logging.getLogger(__name__)


@celery.task(name="billing.expire_trials")
def expire_trials():
    """Expire trial subscriptions past their trial_ends_at.

    Runs hourly via beat schedule. Sets subscription status to 'expired'
    and deactivates the user account so they cannot access the platform.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # Find active trials that are past their end date
        expired_subs = db.execute(
            select(Subscription).where(
                Subscription.status == "trial",
                Subscription.trial_ends_at.isnot(None),
                Subscription.trial_ends_at < now,
            )
        ).scalars().all()

        count = 0
        for sub in expired_subs:
            sub.status = "expired"  # type: ignore[assignment]
            # Deactivate user
            db.execute(
                update(User).where(User.id == sub.user_id).values(is_active=False)
            )
            count += 1
            logger.info(
                "trial_expired",
                extra={"subscription_id": str(sub.id), "user_id": str(sub.user_id)},
            )

        if count:
            db.commit()
            logger.info("expire_trials: %d subscriptions expired", count)
        else:
            logger.debug("expire_trials: no expired trials found")

    except Exception:
        db.rollback()
        logger.exception("expire_trials failed")
        raise
    finally:
        db.close()


@celery.task(name="billing.reset_monthly_usage")
def reset_monthly_usage():
    """Create fresh UsageTracking rows for the new month.

    Runs on the 1st of each month via beat schedule. Creates new rows
    for all active/trial users so counters start at zero.
    """
    db = SessionLocal()
    try:
        period = datetime.now(timezone.utc).strftime("%Y-%m")

        # Find all active subscriptions
        active_subs = db.execute(
            select(Subscription).where(
                Subscription.status.in_(("active", "trial", "pending", "past_due"))
            )
        ).scalars().all()

        count = 0
        for sub in active_subs:
            # Check if row already exists for this period
            existing = db.execute(
                select(UsageTracking).where(
                    UsageTracking.user_id == sub.user_id,
                    UsageTracking.period == period,
                )
            ).scalar_one_or_none()

            if not existing:
                usage = UsageTracking(
                    tenant_id=sub.tenant_id,
                    user_id=sub.user_id,
                    period=period,
                )
                db.add(usage)
                count += 1

        if count:
            db.commit()
            logger.info("reset_monthly_usage: %d new usage rows for period %s", count, period)
        else:
            logger.debug("reset_monthly_usage: no new rows needed for %s", period)

    except Exception:
        db.rollback()
        logger.exception("reset_monthly_usage failed")
        raise
    finally:
        db.close()
