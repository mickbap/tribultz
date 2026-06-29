"""Celery tasks for billing lifecycle — trial expiry and monthly usage reset."""

import logging
from datetime import datetime, timedelta, timezone

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

        from app.services.email_service import send_trial_expired_email

        count = 0
        for sub in expired_subs:
            sub.status = "expired"  # type: ignore[assignment]
            # Deactivate user
            db.execute(
                update(User).where(User.id == sub.user_id).values(is_active=False)
            )
            # Notify user
            user = db.execute(
                select(User).where(User.id == sub.user_id)
            ).scalar_one_or_none()
            if user:
                send_trial_expired_email(
                    to_email=str(user.email),
                    user_name=str(user.full_name),
                )
            # CRM: move deal to closedlost
            from app.tasks.task_crm import crm_sync
            crm_sync.delay(user_id=str(sub.user_id), event_type="trial_expired")
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


@celery.task(name="billing.warn_trial_expiring")
def warn_trial_expiring():
    """Send warning emails for trials expiring in ~3 days or ~1 day.

    Runs hourly at :30. Uses a ±1h window around each threshold so a
    single hourly run covers each user exactly once per warning level.
    """
    from app.services.email_service import send_trial_expiring_email

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        for days_before in (3, 1):
            window_start = now + timedelta(days=days_before) - timedelta(hours=1)
            window_end   = now + timedelta(days=days_before) + timedelta(hours=1)

            subs = db.execute(
                select(Subscription).where(
                    Subscription.status == "trial",
                    Subscription.trial_ends_at >= window_start,
                    Subscription.trial_ends_at < window_end,
                )
            ).scalars().all()

            for sub in subs:
                user = db.execute(
                    select(User).where(User.id == sub.user_id)
                ).scalar_one_or_none()
                if user:
                    send_trial_expiring_email(
                        to_email=str(user.email),
                        user_name=str(user.full_name),
                        days_remaining=days_before,
                    )
                    # CRM: move deal to presentationscheduled on first warning (D-3)
                    if days_before == 3:
                        from app.tasks.task_crm import crm_sync
                        crm_sync.delay(user_id=str(sub.user_id), event_type="trial_expiring")
                    logger.info(
                        "trial_warning_sent",
                        extra={"days": days_before, "user_id": str(sub.user_id)},
                    )

    except Exception:
        logger.exception("warn_trial_expiring failed")
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


@celery.task(name="billing.ga4_purchase")
def ga4_purchase(user_id: str, transaction_id: str, value: float, plan: str) -> dict:
    """Envia o evento `purchase` ao GA4 (Measurement Protocol) após pagamento confirmado.

    Roda fora do request do webhook (não bloqueia a resposta ao ASAAS).
    No-op se GA4_MP_API_SECRET não estiver configurado.
    """
    from app.services.ga4_mp import send_purchase

    sent = send_purchase(
        client_id=user_id,
        transaction_id=transaction_id,
        value=value,
        plan=plan,
        user_id=user_id,
    )
    logger.info("ga4_purchase tx=%s value=%s sent=%s", transaction_id, value, sent)
    return {"sent": sent, "transaction_id": transaction_id}
