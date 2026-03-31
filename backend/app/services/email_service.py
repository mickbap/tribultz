"""Email service — Jinja2 templates + SMTP with graceful degradation.

Templates live in app/templates/emails/*.html.
When EMAIL_VERIFICATION_ENABLED=False (default dev) or SMTP_HOST is empty,
every send call logs the intent and returns True without touching any SMTP server.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings

logger = logging.getLogger(__name__)

# ── Jinja2 environment ────────────────────────────────────────────

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "emails"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _render(template_name: str, **ctx) -> str:
    return _jinja_env.get_template(template_name).render(**ctx)


# ── Public send functions ─────────────────────────────────────────


def send_verification_email(to_email: str, user_name: str, token: str) -> bool:
    """Send the 'Confirm your email' link. Token expires in 24 h."""
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"

    html_body = _render(
        "verify_email.html",
        user_name=user_name,
        verify_url=verify_url,
        frontend_url=settings.FRONTEND_URL,
    )
    text_body = (
        f"Olá, {user_name}!\n\n"
        f"Confirme seu email acessando:\n{verify_url}\n\n"
        "Este link expira em 24 horas.\n"
        "Tribultz Tecnologia Ltda."
    )
    return _send_email(
        to_email=to_email,
        subject="Tribultz — Confirme seu email",
        html_body=html_body,
        text_body=text_body,
        log_url=verify_url,
    )


def send_password_reset_email(to_email: str, user_name: str, token: str) -> bool:
    """Send the 'Reset your password' link. Token expires in 30 min."""
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    html_body = _render(
        "password_reset.html",
        user_name=user_name,
        reset_url=reset_url,
        frontend_url=settings.FRONTEND_URL,
    )
    text_body = (
        f"Olá, {user_name}!\n\n"
        f"Redefina sua senha acessando:\n{reset_url}\n\n"
        "Este link expira em 30 minutos.\n"
        "Se você não solicitou, ignore este email.\n"
        "Tribultz Tecnologia Ltda."
    )
    return _send_email(
        to_email=to_email,
        subject="Tribultz — Redefinir senha",
        html_body=html_body,
        text_body=text_body,
        log_url=reset_url,
    )


def send_payment_confirmation_email(
    to_email: str,
    user_name: str,
    plan_name: str,
    amount_cents: int,
    payment_method: str,
) -> bool:
    """Send the 'Payment confirmed / Premium activated' receipt email."""
    method_labels = {"pix": "PIX", "credit_card": "Cartão de Crédito", "boleto": "Boleto"}
    method_display = method_labels.get(payment_method.lower(), payment_method.upper())
    amount_display = f"R$ {amount_cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # Feature list shown in the email body — generic for all paid plans
    features = [
        "Motor determinístico de validação (CBS/IBS · LC 214 + LC 227)",
        "Memória de Precedentes e contexto fiscal acumulado",
        "Relatórios auditáveis em CSV e PDF",
        "Dashboard de conformidade multi-CNPJ",
        "Validação em lote de documentos XML",
    ]

    html_body = _render(
        "payment_confirmed.html",
        user_name=user_name,
        plan_name=plan_name,
        amount=amount_display,
        payment_method=method_display,
        features=features,
        console_url=f"{settings.FRONTEND_URL}/dashboard",
        frontend_url=settings.FRONTEND_URL,
    )
    text_body = (
        f"Olá, {user_name}!\n\n"
        f"Pagamento confirmado — Plano {plan_name} ativado.\n"
        f"Valor: {amount_display} via {method_display}.\n\n"
        "Acesse o console em: "
        f"{settings.FRONTEND_URL}/dashboard\n\n"
        "Tribultz Tecnologia Ltda."
    )
    return _send_email(
        to_email=to_email,
        subject=f"Tribultz — Plano {plan_name} ativado 🎉",
        html_body=html_body,
        text_body=text_body,
        log_url=f"{settings.FRONTEND_URL}/dashboard",
    )


# ── Internal SMTP sender ──────────────────────────────────────────


def _send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    log_url: str,
) -> bool:
    """Build and dispatch MIMEMultipart email. Logs instead of sending in dev."""
    if not settings.EMAIL_VERIFICATION_ENABLED or not settings.SMTP_HOST:
        logger.info(
            "email_dev_log subject=%r to=%r url=%s",
            subject,
            to_email,
            log_url,
        )
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        if settings.SMTP_TLS:
            server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

        server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()

        logger.info("email_sent subject=%r to=%r", subject, to_email)
        return True

    except Exception:
        logger.exception("email_send_failed subject=%r to=%r", subject, to_email)
        return False
