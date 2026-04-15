"""Billing router — Asaas webhooks, plan info, payments, upgrade, cancel."""

import logging
from datetime import datetime, timezone
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.billing import Payment, Plan, Subscription, UsageTracking
from app.services.asaas_service import asaas
from app.services.email_service import send_payment_confirmation_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


# ── Webhook (public, no auth) ──────────────────────────────────


@router.post("/webhooks/asaas", status_code=200)
async def asaas_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Receive Asaas payment/subscription events.

    Always returns 200 to prevent retries. Validates access token header.
    Idempotent: skips if asaas_payment_id already processed with same status.
    """
    token = request.headers.get("asaas-access-token", "")
    if not asaas.verify_webhook_token(token):
        logger.warning("Webhook rejected: invalid access token")
        return {"status": "ignored", "reason": "invalid token"}

    body = await request.json()
    event = body.get("event", "")
    payment_data = body.get("payment", {})
    asaas_payment_id = payment_data.get("id", "")

    # ── SUBSCRIPTION_DELETED (no payment id in payload) ──────────
    if event == "SUBSCRIPTION_DELETED":
        sub_data = body.get("subscription", {})
        sub_id = sub_data.get("id", "") if isinstance(sub_data, dict) else ""
        if sub_id:
            db.execute(
                update(Subscription)
                .where(Subscription.asaas_subscription_id == sub_id)
                .values(status="cancelled", cancelled_at=datetime.now(timezone.utc))
            )
            db.commit()
            logger.info("Subscription %s cancelled via webhook", sub_id)
        return {"status": "ok", "action": "subscription_cancelled"}

    if not asaas_payment_id:
        logger.info("Webhook %s without payment id, skipping", event)
        return {"status": "ignored", "reason": "no payment id"}

    logger.info("Webhook event=%s payment=%s", event, asaas_payment_id)

    # ── PAYMENT_CONFIRMED / PAYMENT_RECEIVED ──
    if event in ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"):
        payment = db.execute(
            select(Payment).where(Payment.asaas_payment_id == asaas_payment_id)
        ).scalar_one_or_none()

        if not payment:
            logger.warning("Payment %s not found in DB", asaas_payment_id)
            return {"status": "ignored", "reason": "payment not found"}

        if cast(str, payment.status) == "confirmed":
            logger.info("Payment %s already confirmed, idempotent skip", asaas_payment_id)
            return {"status": "ok", "action": "already_confirmed"}

        # Update payment
        payment.status = "confirmed"  # type: ignore[assignment]
        payment.paid_at = datetime.now(timezone.utc)  # type: ignore[assignment]

        # Activate subscription
        db.execute(
            update(Subscription)
            .where(Subscription.id == payment.subscription_id)
            .values(status="active", current_period_start=datetime.now(timezone.utc))
        )

        # Activate user (skip if LGPD-deleted)
        sub = db.execute(
            select(Subscription).where(Subscription.id == payment.subscription_id)
        ).scalar_one_or_none()
        if sub:
            user = db.get(User, sub.user_id)
            if user and user.deleted_at is None:
                db.execute(
                    update(User).where(User.id == sub.user_id).values(is_active=True)
                )
            elif user and user.deleted_at is not None:
                logger.warning(
                    "Skipping activation for LGPD-deleted user %s (payment %s)",
                    sub.user_id, asaas_payment_id,
                )

        db.commit()
        logger.info("Payment %s confirmed, subscription activated", asaas_payment_id)

        # ── Payment confirmation e-mail ───────────────────────
        if sub:
            logger.info(
                "PAYMENT_CONFIRMED audit | asaas_payment_id=%s user_id=%s subscription_id=%s",
                asaas_payment_id,
                sub.user_id,
                sub.id,
            )
            # Fetch user + plan for the email
            confirmed_user = db.execute(
                select(User).where(User.id == sub.user_id)
            ).scalar_one_or_none()
            confirmed_plan = db.execute(
                select(Plan).where(Plan.id == sub.plan_id)
            ).scalar_one_or_none()
            if confirmed_user and confirmed_plan:
                send_payment_confirmation_email(
                    to_email=str(confirmed_user.email),
                    user_name=str(confirmed_user.full_name),
                    plan_name=str(confirmed_plan.name),
                    amount_cents=int(confirmed_plan.price_cents),  # type: ignore[arg-type]
                    payment_method=str(payment.payment_method),
                )

        return {"status": "ok", "action": "payment_confirmed"}

    # ── PAYMENT_OVERDUE ──
    if event == "PAYMENT_OVERDUE":
        payment = db.execute(
            select(Payment).where(Payment.asaas_payment_id == asaas_payment_id)
        ).scalar_one_or_none()

        if payment and cast(str, payment.status) != "overdue":
            payment.status = "overdue"  # type: ignore[assignment]
            db.execute(
                update(Subscription)
                .where(Subscription.id == payment.subscription_id)
                .values(status="past_due")
            )
            db.commit()
            logger.info("Payment %s overdue, subscription past_due", asaas_payment_id)

        return {"status": "ok", "action": "payment_overdue"}

    logger.info("Webhook event %s not handled, ignoring", event)
    return {"status": "ignored", "reason": "unhandled event"}


# ── Billing info (authenticated) ───────────────────────────────


@router.get("/me")
def billing_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return current user's plan, subscription status, and usage."""
    result = db.execute(
        select(Subscription, Plan)
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    ).first()

    if not result:
        return {
            "plan_slug": None,
            "plan_name": None,
            "status": None,
            "usage": None,
            "trial_ends_at": None,
        }

    sub, plan = result

    # Get current usage
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = db.execute(
        select(UsageTracking).where(
            UsageTracking.user_id == current_user.id,
            UsageTracking.period == period,
        )
    ).scalar_one_or_none()

    return {
        "plan_slug": cast(str, plan.slug),
        "plan_name": cast(str, plan.name),
        "price_cents": cast(int, plan.price_cents),
        "status": cast(str, sub.status),
        "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
        "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "max_validations": plan.max_validations,
        "max_ai_messages": plan.max_ai_messages,
        "has_pdf_reports": cast(bool, plan.has_pdf_reports),
        "has_batch": cast(bool, plan.has_batch),
        "has_dashboard": cast(bool, plan.has_dashboard),
        "usage": {
            "validations_used": cast(int, usage.validations_used) if usage else 0,
            "ai_messages_used": cast(int, usage.ai_messages_used) if usage else 0,
            "period": period,
        },
    }


@router.get("/payments")
def list_payments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return payment history for current user."""
    rows = db.execute(
        select(Payment)
        .join(Subscription, Payment.subscription_id == Subscription.id)
        .where(Subscription.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
    ).scalars().all()

    return [
        {
            "id": str(p.id),
            "amount_cents": cast(int, p.amount_cents),
            "status": cast(str, p.status),
            "payment_method": cast(str, p.payment_method),
            "paid_at": cast(datetime, p.paid_at).isoformat() if p.paid_at is not None else None,
            "created_at": cast(datetime, p.created_at).isoformat() if p.created_at is not None else None,
        }
        for p in rows
    ]


@router.post("/upgrade")
async def upgrade_plan(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upgrade to a higher plan. Creates new Asaas payment."""
    body = await request.json()
    target_slug = body.get("plan_slug", "")
    billing_type = body.get("billing_type", "PIX")

    # Validate target plan
    target_plan = db.execute(
        select(Plan).where(Plan.slug == target_slug, Plan.is_active == True)  # noqa: E712
    ).scalar_one_or_none()
    if not target_plan:
        raise HTTPException(status_code=400, detail="Plano não encontrado.")

    if cast(int, target_plan.price_cents) == 0:
        raise HTTPException(status_code=400, detail="Não é possível fazer upgrade para plano gratuito.")

    # Get current subscription
    current_sub = db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if not current_sub:
        raise HTTPException(status_code=400, detail="Nenhuma assinatura encontrada.")

    # Cancel old Asaas subscription if exists
    asaas_sub_id = cast(str, current_sub.asaas_subscription_id) if current_sub.asaas_subscription_id is not None else None
    if asaas_sub_id:
        try:
            await asaas.cancel_subscription(asaas_sub_id)
        except Exception:
            logger.warning("Falha ao cancelar assinatura Asaas anterior: %s", asaas_sub_id)

    # Mark old subscription as cancelled
    current_sub.status = "cancelled"  # type: ignore[assignment]
    current_sub.cancelled_at = datetime.now(timezone.utc)  # type: ignore[assignment]

    # Create new Asaas payment
    value = cast(int, target_plan.price_cents) / 100.0
    checkout_url = None
    pix_qr_code = None
    pix_copy_paste = None

    # Validate CNPJ before calling Asaas (avoids 502 / CORS-less error on empty CNPJ)
    cnpj_value = cast(str, current_user.cnpj).strip() if current_user.cnpj is not None else ""
    customer_id = cast(str, current_sub.asaas_customer_id) if current_sub.asaas_customer_id is not None else None
    if not customer_id and len(cnpj_value.replace(".", "").replace("/", "").replace("-", "")) not in (11, 14):
        raise HTTPException(
            status_code=400,
            detail="Informe seu CNPJ nas configurações antes de fazer upgrade.",
        )

    try:
        if not customer_id:
            cust = await asaas.create_customer(
                name=cast(str, current_user.full_name),
                email=cast(str, current_user.email),
                cpf_cnpj=cnpj_value,
                phone=cast(str, current_user.phone) if current_user.phone is not None else "",
            )
            customer_id = cust["id"]

        payment_resp = await asaas.create_payment(
            customer_id=customer_id,
            value=value,
            billing_type=billing_type.upper(),
            description=f"Upgrade Tribultz — {cast(str, target_plan.name)}",
        )
        asaas_payment_id = payment_resp["id"]

        if billing_type.upper() == "PIX":
            pix_data = await asaas.get_pix_qr_code(asaas_payment_id)
            pix_qr_code = pix_data.get("encodedImage")
            pix_copy_paste = pix_data.get("payload")
        else:
            checkout_url = asaas.get_checkout_url(asaas_payment_id)
    except Exception:
        logger.exception("Erro ao criar pagamento Asaas no upgrade")
        raise HTTPException(status_code=502, detail="Erro ao processar pagamento. Tente novamente.")

    # Create new subscription
    new_sub = Subscription(
        tenant_id=current_sub.tenant_id,
        user_id=current_user.id,
        plan_id=target_plan.id,
        status="pending",
        asaas_customer_id=customer_id,
    )
    db.add(new_sub)
    db.flush()

    # Create payment record
    new_payment = Payment(
        tenant_id=current_sub.tenant_id,
        subscription_id=new_sub.id,
        asaas_payment_id=asaas_payment_id,
        amount_cents=cast(int, target_plan.price_cents),
        status="pending",
        payment_method=billing_type.lower(),
        pix_qr_code=pix_qr_code,
        pix_copy_paste=pix_copy_paste,
    )
    db.add(new_payment)
    db.commit()

    return {
        "subscription_id": str(new_sub.id),
        "plan_slug": cast(str, target_plan.slug),
        "status": "pending",
        "checkout_url": checkout_url,
        "pix_qr_code": pix_qr_code,
        "pix_copy_paste": pix_copy_paste,
    }


@router.post("/cancel")
async def cancel_subscription_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel the current subscription."""
    sub = db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_(("active", "trial", "pending", "past_due")),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if not sub:
        raise HTTPException(status_code=400, detail="Nenhuma assinatura ativa encontrada.")

    # Cancel in Asaas if applicable
    cancel_sub_id = cast(str, sub.asaas_subscription_id) if sub.asaas_subscription_id is not None else None
    if cancel_sub_id:
        try:
            await asaas.cancel_subscription(cancel_sub_id)
        except Exception:
            logger.warning("Falha ao cancelar assinatura Asaas: %s", cancel_sub_id)

    sub.status = "cancelled"  # type: ignore[assignment]
    sub.cancelled_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    # User keeps access until current_period_end — do NOT deactivate
    db.commit()

    period_end = sub.current_period_end.isoformat() if sub.current_period_end is not None else None

    return {
        "status": "cancelled",
        "message": "Assinatura cancelada. Acesso mantido até o fim do período atual.",
        "access_until": period_end,
    }
