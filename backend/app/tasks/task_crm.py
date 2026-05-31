"""CRM tasks — deterministic HubSpot sync + LLM engagement crew + daily audit.

Two-layer architecture:
  crm.sync       — deterministic, called on every lifecycle event. No LLM.
                   Upserts contact/company/deal in HubSpot and returns immediately.
  crm.engagement — LLM crew for dunning and win-back emails. Triggered only on
                   payment_overdue and subscription_cancelled events.
  crm.audit      — Daily reconciliation. Re-syncs all subscriptions updated in last 24h.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.celery_app import celery
from app.database import SessionLocal
from app.models.auth import Tenant, User
from app.models.billing import Plan, Subscription

logger = logging.getLogger(__name__)

# ── Deal stage mapping ─────────────────────────────────────────

DEAL_STAGE_MAP: dict[str, str] = {
    # Mapeado para o pipeline padrão do HubSpot (conta free — stages fixos)
    "register":                "appointmentscheduled",   # Trial Iniciado       (20%)
    "trial_expiring":          "qualifiedtobuy",         # Trial Expirando      (40%)
    "trial_expired":           "closedlost",             # Cliente Perdido      (0%)
    "payment_confirmed":       "closedwon",              # Cliente Ativo        (100%)
    "payment_overdue":         "decisionmakerboughtin",  # Tomador de Decisão   (80%) — em risco
    "subscription_cancelled":  "closedlost",             # Cliente Perdido      (0%)
    "subscription_pending":    "presentationscheduled",  # Pagamento Pendente   (60%)
}


def _load_crm_context(db, user_id: str) -> dict | None:
    """Return user + subscription + plan + tenant data for a given user_id."""
    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    if not user:
        return None

    tenant = db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    ).scalar_one_or_none()

    sub_row = db.execute(
        select(Subscription, Plan)
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    ).first()

    sub, plan = sub_row if sub_row else (None, None)

    return {
        "user": user,
        "tenant": tenant,
        "subscription": sub,
        "plan": plan,
    }


# ── crm.sync — deterministic HubSpot contact/deal sync ────────


@celery.task(name="crm.sync", bind=True, max_retries=2)
def crm_sync(self, user_id: str, event_type: str) -> dict:
    """Upsert HubSpot contact + company + deal for a lifecycle event.

    Idempotent: HubSpot upsert_contact and upsert_deal are safe to re-run.
    Silently skips if HUBSPOT_ENABLED is False.
    """
    from app.tools.hubspot_tool import upsert_contact, upsert_company, upsert_deal, log_note
    from app.config import settings

    db = SessionLocal()
    try:
        ctx = _load_crm_context(db, user_id)
        if not ctx:
            logger.warning("crm.sync: user not found user_id=%s", user_id)
            return {"status": "user_not_found"}

        user = ctx["user"]
        tenant = ctx["tenant"]
        sub = ctx["subscription"]
        plan = ctx["plan"]

        email = str(user.email)
        full_name = str(user.full_name)
        company_name = str(tenant.name) if tenant else f"Empresa {email}"
        tenant_slug = str(tenant.slug) if tenant else ""
        plan_slug = str(plan.slug) if plan else "trial"
        plan_price_cents = int(plan.price_cents) if plan else 0  # type: ignore[arg-type]
        sub_status = str(sub.status) if sub else "unknown"
        deal_stage = DEAL_STAGE_MAP.get(event_type, "qualifiedtobuy")

        # 1. Upsert contact — apenas propriedades padrão HubSpot
        first_name = full_name.split()[0] if full_name else full_name
        last_name = " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else ""
        upsert_contact(
            email=email,
            first_name=first_name,
            last_name=last_name,
        )

        # 2. Upsert company — apenas propriedades padrão HubSpot
        company_result = upsert_company(
            name=company_name,
        )

        # 3. Upsert deal — stage codifica o ciclo de vida, sem custom props
        deal_name = f"Tribultz — {company_name} ({tenant_slug})"
        upsert_deal(
            deal_name=deal_name,
            stage=deal_stage,
            amount=plan_price_cents / 100.0 if plan_price_cents else None,
        )

        # 4. Log sync note to company
        company_id = company_result.get("id", "") if isinstance(company_result, dict) else ""
        if company_id and settings.HUBSPOT_ENABLED:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log_note(
                object_type="companies",
                object_id=company_id,
                body=(
                    f"Tribultz CRM sync — {today}\n"
                    f"Evento: {event_type}\n"
                    f"Status: {sub_status} | Plano: {plan_slug} | Stage: {deal_stage}"
                ),
            )

        logger.info(
            "crm.sync ok event=%s user_id=%s deal_stage=%s hubspot=%s",
            event_type, user_id, deal_stage, settings.HUBSPOT_ENABLED,
        )
        return {
            "status": "ok",
            "event_type": event_type,
            "deal_stage": deal_stage,
            "hubspot_enabled": settings.HUBSPOT_ENABLED,
        }

    except Exception as exc:
        logger.exception("crm.sync failed event=%s user_id=%s", event_type, user_id)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


# ── crm.engagement — LLM crew for dunning / win-back ──────────


@celery.task(name="crm.engagement", bind=True, max_retries=1)
def crm_engagement(self, user_id: str, event_type: str) -> dict:
    """Run the CRMEngagementCrew to compose and send a personalized email.

    Falls back to send_payment_overdue_email() if LLM is unavailable.
    Only handles: payment_overdue, subscription_cancelled.
    """
    from app.crews.crm_engagement_crew import CRMEngagementCrew
    from app.crews.llm_config import LLMUnavailableError
    from app.services.email_service import send_payment_overdue_email

    db = SessionLocal()
    try:
        ctx = _load_crm_context(db, user_id)
        if not ctx:
            logger.warning("crm.engagement: user not found user_id=%s", user_id)
            return {"status": "user_not_found"}

        user = ctx["user"]
        tenant = ctx["tenant"]

        to_email = str(user.email)
        user_name = str(user.full_name)
        company_name = str(tenant.name) if tenant else f"Empresa {to_email}"
        tenant_id = str(user.tenant_id)

    except Exception:
        logger.exception("crm.engagement DB query failed user_id=%s", user_id)
        return {"status": "db_error"}
    finally:
        db.close()

    try:
        crew = CRMEngagementCrew(
            user_id=user_id,
            tenant_id=tenant_id,
            event_type=event_type,
            to_email=to_email,
            user_name=user_name,
            company_name=company_name,
        )
        result = crew.run()

        if result.get("status") == "llm_unavailable":
            # LLM exhausted — send static fallback for dunning
            if event_type == "payment_overdue":
                send_payment_overdue_email(to_email=to_email, user_name=user_name)
                logger.info(
                    "crm.engagement fallback template sent event=%s user_id=%s",
                    event_type, user_id,
                )
            else:
                logger.info(
                    "crm.engagement no fallback template for event=%s, skipping",
                    event_type,
                )

        logger.info(
            "crm.engagement done event=%s user_id=%s status=%s",
            event_type, user_id, result.get("status"),
        )
        return result

    except LLMUnavailableError:
        if event_type == "payment_overdue":
            send_payment_overdue_email(to_email=to_email, user_name=user_name)
        return {"status": "llm_unavailable", "event_type": event_type}

    except Exception as exc:
        logger.exception("crm.engagement failed event=%s user_id=%s", event_type, user_id)
        raise self.retry(exc=exc, countdown=300)


# ── crm.audit — daily reconciliation ──────────────────────────


@celery.task(name="crm.audit")
def crm_audit() -> dict:
    """Re-sync all subscriptions updated in the last 24h with HubSpot.

    Runs daily at 09:00. Sends crm.sync.delay() for each stale subscription.
    Filters by updated_at to avoid unnecessary API calls.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        subs = db.execute(
            select(Subscription)
            .where(Subscription.updated_at >= cutoff)
        ).scalars().all()

        count = 0
        for sub in subs:
            event_type = _status_to_event(str(sub.status))
            crm_sync.delay(user_id=str(sub.user_id), event_type=event_type)
            count += 1

        logger.info("crm.audit dispatched %d sync tasks (cutoff=%s)", count, cutoff.isoformat())
        return {"status": "ok", "dispatched": count}
    except Exception:
        logger.exception("crm.audit failed")
        return {"status": "error"}
    finally:
        db.close()


def _status_to_event(status: str) -> str:
    return {
        "trial": "register",
        "active": "payment_confirmed",
        "pending": "subscription_pending",
        "past_due": "payment_overdue",
        "cancelled": "subscription_cancelled",
        "expired": "trial_expired",
    }.get(status, "register")
