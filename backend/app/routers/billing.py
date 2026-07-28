"""Billing router — Asaas webhooks, plan info, payments, upgrade, cancel."""

import logging
from datetime import datetime, timedelta, timezone
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.admin_audit import AdminAuditLog
from app.models.auth import User
from app.models.billing import Payment, Plan, Subscription, UsageTracking
from app.services.asaas_service import asaas
from app.services.email_service import send_ops_alert, send_payment_confirmation_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def _audit_billing_event(
    db: Session,
    *,
    event: str,
    target_type: str,
    target_id: str,
    detail: dict,
) -> None:
    """Log a billing webhook event to AdminAuditLog (12 meses de retenção, Escopo 5.3).

    Eventos de webhook não têm um admin como ator — actor_email marca a
    origem como o próprio gateway, para diferenciar de ações manuais.
    """
    db.add(
        AdminAuditLog(
            actor_user_id=None,
            actor_email="system:asaas-webhook",
            action=event,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
    )


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
            cancelled_sub = db.execute(
                select(Subscription).where(Subscription.asaas_subscription_id == sub_id)
            ).scalar_one_or_none()
            db.execute(
                update(Subscription)
                .where(Subscription.asaas_subscription_id == sub_id)
                .values(status="cancelled", cancelled_at=datetime.now(timezone.utc))
            )
            _audit_billing_event(
                db, event=event, target_type="subscription", target_id=sub_id,
                detail={"user_id": str(cancelled_sub.user_id)} if cancelled_sub else {},
            )
            db.commit()
            logger.info("Subscription %s cancelled via webhook", sub_id)
            if cancelled_sub:
                from app.tasks.task_crm import crm_sync, crm_engagement
                crm_sync.delay(user_id=str(cancelled_sub.user_id), event_type="subscription_cancelled")
                crm_engagement.delay(user_id=str(cancelled_sub.user_id), event_type="subscription_cancelled")
                send_ops_alert(
                    "Assinatura cancelada",
                    f"Subscription {sub_id} (user {cancelled_sub.user_id}) foi cancelada via webhook Asaas.",
                )
        return {"status": "ok", "action": "subscription_cancelled"}

    # ── SUBSCRIPTION_CREATED / SUBSCRIPTION_UPDATED (no payment id either) ──
    # A assinatura já é criada pelo próprio app (endpoint /upgrade) — estes eventos
    # são só confirmação/sincronização do lado da Asaas, registrados para auditoria.
    if event in ("SUBSCRIPTION_CREATED", "SUBSCRIPTION_UPDATED"):
        sub_data = body.get("subscription", {})
        sub_id = sub_data.get("id", "") if isinstance(sub_data, dict) else ""
        if sub_id:
            _audit_billing_event(
                db, event=event, target_type="subscription", target_id=sub_id,
                detail={"raw": sub_data} if isinstance(sub_data, dict) else {},
            )
            db.commit()
        return {"status": "ok", "action": event.lower()}

    if not asaas_payment_id:
        logger.info("Webhook %s without payment id, skipping", event)
        return {"status": "ignored", "reason": "no payment id"}

    logger.info("Webhook event=%s payment=%s", event, asaas_payment_id)

    # ── PAYMENT_CONFIRMED / PAYMENT_RECEIVED ──
    if event in ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"):
        now = datetime.now(timezone.utc)
        payment = db.execute(
            select(Payment).where(Payment.asaas_payment_id == asaas_payment_id)
        ).scalar_one_or_none()

        if not payment:
            # Unknown payment — may be a monthly renewal from an Asaas subscription
            asaas_sub_id = payment_data.get("subscription") or payment_data.get("subscriptionId", "")
            if asaas_sub_id:
                sub = db.execute(
                    select(Subscription).where(Subscription.asaas_subscription_id == asaas_sub_id)
                ).scalar_one_or_none()
                if sub:
                    renewal = Payment(
                        tenant_id=sub.tenant_id,
                        subscription_id=sub.id,
                        asaas_payment_id=asaas_payment_id,
                        amount_cents=int(float(payment_data.get("value", 0)) * 100),
                        status="confirmed",
                        payment_method=payment_data.get("billingType", "PIX").lower(),
                        paid_at=now,
                    )
                    db.add(renewal)
                    db.execute(
                        update(Subscription)
                        .where(Subscription.id == sub.id)
                        .values(
                            status="active",
                            current_period_start=now,
                            current_period_end=now + timedelta(days=30),
                        )
                    )
                    db.commit()
                    logger.info(
                        "Renewal confirmed | payment=%s subscription=%s", asaas_payment_id, sub.id
                    )
                    from app.tasks.task_crm import crm_sync
                    crm_sync.delay(user_id=str(sub.user_id), event_type="payment_confirmed")
                    return {"status": "ok", "action": "renewal_confirmed"}
            logger.warning("Payment %s not found in DB", asaas_payment_id)
            return {"status": "ignored", "reason": "payment not found"}

        if cast(str, payment.status) == "confirmed":
            logger.info("Payment %s already confirmed, idempotent skip", asaas_payment_id)
            return {"status": "ok", "action": "already_confirmed"}

        # Update payment
        payment.status = "confirmed"  # type: ignore[assignment]
        payment.paid_at = now  # type: ignore[assignment]

        # Activate subscription + extend period
        db.execute(
            update(Subscription)
            .where(Subscription.id == payment.subscription_id)
            .values(
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )

        # Activate user + auto-verify email (skip if LGPD-deleted)
        sub = db.execute(
            select(Subscription).where(Subscription.id == payment.subscription_id)
        ).scalar_one_or_none()
        if sub:
            user = db.get(User, sub.user_id)
            if user and user.deleted_at is None:
                db.execute(
                    update(User)
                    .where(User.id == sub.user_id)
                    .values(is_active=True, email_verified=True)
                )
            elif user and user.deleted_at is not None:
                logger.warning(
                    "Skipping activation for LGPD-deleted user %s (payment %s)",
                    sub.user_id, asaas_payment_id,
                )

        _audit_billing_event(
            db, event=event, target_type="payment", target_id=asaas_payment_id,
            detail={"user_id": str(sub.user_id)} if sub else {},
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
                send_ops_alert(
                    "Pagamento confirmado",
                    f"Usuário: {confirmed_user.email}\nPlano: {confirmed_plan.name}\n"
                    f"Valor: R$ {int(confirmed_plan.price_cents) / 100:.2f}\n"
                    f"Método: {payment.payment_method}\nAsaas payment id: {asaas_payment_id}",
                )
            # CRM sync: move deal to closedwon
            from app.tasks.task_crm import crm_sync
            crm_sync.delay(user_id=str(sub.user_id), event_type="payment_confirmed")

            # GA4 purchase (server-side): receita por usuário/canal. No-op sem secret.
            if confirmed_plan:
                from app.tasks.task_g_billing import ga4_purchase
                ga4_purchase.delay(
                    user_id=str(sub.user_id),
                    transaction_id=str(asaas_payment_id),
                    value=round(int(confirmed_plan.price_cents) / 100, 2),  # type: ignore[arg-type]
                    plan=str(confirmed_plan.name),
                )

        return {"status": "ok", "action": "payment_confirmed"}

    # ── PAYMENT_OVERDUE ──
    if event == "PAYMENT_OVERDUE":
        payment = db.execute(
            select(Payment).where(Payment.asaas_payment_id == asaas_payment_id)
        ).scalar_one_or_none()

        if payment and cast(str, payment.status) != "overdue":
            payment.status = "overdue"  # type: ignore[assignment]
            sub_overdue = db.execute(
                select(Subscription).where(Subscription.id == payment.subscription_id)
            ).scalar_one_or_none()
            db.execute(
                update(Subscription)
                .where(Subscription.id == payment.subscription_id)
                .values(status="past_due")
            )
            _audit_billing_event(
                db, event=event, target_type="payment", target_id=asaas_payment_id,
                detail={"user_id": str(sub_overdue.user_id)} if sub_overdue else {},
            )
            db.commit()
            logger.info("Payment %s overdue, subscription past_due", asaas_payment_id)
            if sub_overdue:
                from app.tasks.task_crm import crm_sync, crm_engagement
                crm_sync.delay(user_id=str(sub_overdue.user_id), event_type="payment_overdue")
                crm_engagement.delay(user_id=str(sub_overdue.user_id), event_type="payment_overdue")
                send_ops_alert(
                    "Pagamento em atraso",
                    f"Payment {asaas_payment_id} (user {sub_overdue.user_id}) marcado como overdue. "
                    "Assinatura movida para past_due.",
                )

        return {"status": "ok", "action": "payment_overdue"}

    # ── PAYMENT_CREDIT_CARD_CAPTURE_REFUSED (cartão recusado) ──
    # Asaas já reprocessa a cobrança automaticamente (5 tentativas em ~2 dias:
    # 8h/14h/20h no vencimento + 2 tentativas no dia seguinte) antes de emitir
    # PAYMENT_OVERDUE — não suspendemos aqui, só registramos e avisamos.
    if event == "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED":
        payment = db.execute(
            select(Payment).where(Payment.asaas_payment_id == asaas_payment_id)
        ).scalar_one_or_none()
        if payment and cast(str, payment.status) not in ("confirmed", "failed"):
            payment.status = "failed"  # type: ignore[assignment]
            sub_declined = db.execute(
                select(Subscription).where(Subscription.id == payment.subscription_id)
            ).scalar_one_or_none()
            _audit_billing_event(
                db, event=event, target_type="payment", target_id=asaas_payment_id,
                detail={"user_id": str(sub_declined.user_id)} if sub_declined else {},
            )
            db.commit()
            logger.info("Payment %s card declined, Asaas will retry automatically", asaas_payment_id)
            if sub_declined:
                from app.tasks.task_crm import crm_engagement
                crm_engagement.delay(user_id=str(sub_declined.user_id), event_type="payment_overdue")
                send_ops_alert(
                    "Cartão recusado",
                    f"Payment {asaas_payment_id} (user {sub_declined.user_id}) teve captura recusada. "
                    "Asaas reprocessará automaticamente (até 5 tentativas em ~2 dias).",
                )
        return {"status": "ok", "action": "payment_declined"}

    # ── PAYMENT_REFUNDED / PAYMENT_PARTIALLY_REFUNDED ──
    if event in ("PAYMENT_REFUNDED", "PAYMENT_PARTIALLY_REFUNDED"):
        payment = db.execute(
            select(Payment).where(Payment.asaas_payment_id == asaas_payment_id)
        ).scalar_one_or_none()
        if payment and cast(str, payment.status) != "refunded":
            payment.status = "refunded"  # type: ignore[assignment]
            sub_refunded = db.execute(
                select(Subscription).where(Subscription.id == payment.subscription_id)
            ).scalar_one_or_none()
            if sub_refunded and cast(str, sub_refunded.status) not in ("cancelled",):
                db.execute(
                    update(Subscription)
                    .where(Subscription.id == payment.subscription_id)
                    .values(status="cancelled", cancelled_at=datetime.now(timezone.utc))
                )
            _audit_billing_event(
                db, event=event, target_type="payment", target_id=asaas_payment_id,
                detail={"user_id": str(sub_refunded.user_id)} if sub_refunded else {},
            )
            db.commit()
            logger.warning("Payment %s refunded, access revoked — verificar manualmente", asaas_payment_id)
            if sub_refunded:
                send_ops_alert(
                    "Reembolso processado — verificar",
                    f"Payment {asaas_payment_id} (user {sub_refunded.user_id}) foi reembolsado pela Asaas. "
                    "Assinatura cancelada e acesso revogado automaticamente.",
                )
        return {"status": "ok", "action": "payment_refunded"}

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

    # ── Proporcionalidade (Escopo 3.2) ──────────────────────────
    # Crédito pelos dias não usados do plano atual, abatido do primeiro
    # pagamento do novo plano. Sem crédito (ex.: upgrade a partir do trial,
    # sem período pago corrente) → comportamento cheio, sem proporção.
    old_plan = db.execute(
        select(Plan).where(Plan.id == current_sub.plan_id)
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    days_remaining = 0
    if current_sub.current_period_end is not None:
        period_end = cast(datetime, current_sub.current_period_end)
        if period_end > now:
            days_remaining = min(30, (period_end - now).days)

    old_price_cents = cast(int, old_plan.price_cents) if old_plan is not None else 0
    target_price_cents = cast(int, target_plan.price_cents)
    credit_cents = (old_price_cents * days_remaining) // 30 if days_remaining > 0 else 0
    prorated_charge_cents = max(0, target_price_cents - credit_cents)
    has_proration = credit_cents > 0 and prorated_charge_cents < target_price_cents

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
    value = target_price_cents / 100.0
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

        if has_proration:
            # Cobrança avulsa proporcional agora; a assinatura recorrente (valor
            # cheio) só gera o próximo pagamento quando o período antigo acabaria
            # — evita cobrar o valor cheio duas vezes no mesmo ciclo.
            prorated_payment = await asaas.create_payment(
                customer_id=customer_id,
                value=prorated_charge_cents / 100.0,
                billing_type=billing_type.upper(),
                description=f"Upgrade Tribultz — {cast(str, target_plan.name)} (proporcional)",
            )
            asaas_payment_id = prorated_payment["id"]

            next_due = cast(datetime, current_sub.current_period_end).strftime("%Y-%m-%d")
            sub_resp = await asaas.create_subscription(
                customer_id=customer_id,
                value=value,
                billing_type=billing_type.upper(),
                description=f"Assinatura Tribultz — {cast(str, target_plan.name)}",
                next_due_date=next_due,
            )
            new_asaas_sub_id = sub_resp["id"]
        else:
            # Create recurring Asaas subscription (monthly)
            sub_resp = await asaas.create_subscription(
                customer_id=customer_id,
                value=value,
                billing_type=billing_type.upper(),
                description=f"Upgrade Tribultz — {cast(str, target_plan.name)}",
            )
            new_asaas_sub_id = sub_resp["id"]

            # Retrieve first payment created automatically by Asaas
            sub_payments = await asaas.get_subscription_payments(new_asaas_sub_id)
            if not sub_payments:
                raise ValueError("Asaas subscription created but no payment found")
            first_payment = sub_payments[0]
            asaas_payment_id = first_payment["id"]

        if billing_type.upper() == "PIX":
            pix_data = await asaas.get_pix_qr_code(asaas_payment_id)
            pix_qr_code = pix_data.get("encodedImage")
            pix_copy_paste = pix_data.get("payload")
        else:
            checkout_url = asaas.get_checkout_url(asaas_payment_id)
    except Exception:
        logger.exception("Erro ao criar assinatura Asaas no upgrade")
        raise HTTPException(status_code=502, detail="Erro ao processar pagamento. Tente novamente.")

    # Create new subscription
    new_sub = Subscription(
        tenant_id=current_sub.tenant_id,
        user_id=current_user.id,
        plan_id=target_plan.id,
        status="pending",
        asaas_customer_id=customer_id,
        asaas_subscription_id=new_asaas_sub_id,
    )
    db.add(new_sub)
    db.flush()

    # Create payment record — valor proporcional quando há crédito do plano anterior
    charged_cents = prorated_charge_cents if has_proration else target_price_cents
    new_payment = Payment(
        tenant_id=current_sub.tenant_id,
        subscription_id=new_sub.id,
        asaas_payment_id=asaas_payment_id,
        amount_cents=charged_cents,
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
        "amount_charged_cents": charged_cents,
        "prorated": has_proration,
    }


@router.post("/cancel")
async def cancel_subscription_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel the current subscription.

    Direito de arrependimento (CDC art. 49, Política de Reembolso, #4): se o
    cancelamento ocorre até 7 dias da primeira assinatura do usuário —
    contratação "fora do estabelecimento comercial" — reembolsa integralmente
    tudo que foi pago no período e revoga o acesso imediatamente. Depois dos
    7 dias, comportamento padrão: sem reembolso, acesso até o fim do período.
    """
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

    now = datetime.now(timezone.utc)

    # Direito de arrependimento: ancorado na PRIMEIRA assinatura do usuário
    # (não reseta a cada upgrade) — "durante o prazo de reflexão" (CDC art. 49).
    earliest_sub = db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    contract_start = cast(datetime, earliest_sub.created_at) if earliest_sub is not None else now
    within_withdrawal_window = (now - contract_start) <= timedelta(days=7)

    refunded_cents = 0
    if within_withdrawal_window:
        confirmed_payments = db.execute(
            select(Payment)
            .join(Subscription, Payment.subscription_id == Subscription.id)
            .where(
                Subscription.user_id == current_user.id,
                Payment.status == "confirmed",
            )
        ).scalars().all()

        for payment in confirmed_payments:
            try:
                await asaas.refund_payment(
                    cast(str, payment.asaas_payment_id),
                    description="Direito de arrependimento (CDC art. 49) — cancelamento em até 7 dias.",
                )
                payment.status = "refunded"  # type: ignore[assignment]
                refunded_cents += cast(int, payment.amount_cents)
            except Exception:
                logger.exception(
                    "Falha ao estornar pagamento %s (direito de arrependimento)",
                    payment.asaas_payment_id,
                )

        # Revoga acesso imediatamente — o contrato foi desfeito, não só cancelado
        # para o futuro. Encerra TODAS as assinaturas não-canceladas do usuário.
        db.execute(
            update(Subscription)
            .where(
                Subscription.user_id == current_user.id,
                Subscription.status != "cancelled",
            )
            .values(status="cancelled", cancelled_at=now, current_period_end=now)
        )
        _audit_billing_event(
            db, event="WITHDRAWAL_REFUND_7_DAYS", target_type="subscription", target_id=str(sub.id),
            detail={"user_id": str(current_user.id), "refunded_cents": refunded_cents},
        )
        db.commit()

        send_ops_alert(
            "Direito de arrependimento exercido (CDC art. 49)",
            f"Usuário: {current_user.email}\nSubscription: {sub.id}\n"
            f"Reembolsado: R$ {refunded_cents / 100:.2f}\nAcesso revogado imediatamente.",
        )

        return {
            "status": "cancelled",
            "message": "Cancelado dentro do prazo de arrependimento (7 dias). Reembolso integral processado.",
            "access_until": now.isoformat(),
            "refunded": True,
            "refunded_cents": refunded_cents,
        }

    sub.status = "cancelled"  # type: ignore[assignment]
    sub.cancelled_at = now  # type: ignore[assignment]
    # User keeps access until current_period_end — do NOT deactivate
    db.commit()

    period_end = sub.current_period_end.isoformat() if sub.current_period_end is not None else None

    return {
        "status": "cancelled",
        "message": "Assinatura cancelada. Acesso mantido até o fim do período atual.",
        "access_until": period_end,
        "refunded": False,
        "refunded_cents": 0,
    }
