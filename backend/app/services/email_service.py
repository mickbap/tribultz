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
    method_labels = {"pix": "PIX", "credit_card": "Cartão de Crédito"}
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


def send_support_ticket_email(
    to_email: str,
    user_name: str,
    ticket_title: str,
    priority: str,
) -> bool:
    """Notify user that their support ticket was received."""
    priority_labels = {"low": "Baixa", "medium": "Média", "high": "Alta", "critical": "Crítica"}
    html_body = _render(
        "support_ticket_created.html",
        user_name=user_name,
        ticket_title=ticket_title,
        priority=priority_labels.get(priority, priority.capitalize()),
        console_url=f"{settings.FRONTEND_URL}/support",
        frontend_url=settings.FRONTEND_URL,
    )
    text_body = (
        f"Olá, {user_name}!\n\n"
        f"Ticket aberto: {ticket_title}\n"
        f"Prioridade: {priority_labels.get(priority, priority)}\n\n"
        "Nossa equipe irá responder em breve.\n"
        f"Acompanhe em: {settings.FRONTEND_URL}/support\n\n"
        "Tribultz Tecnologia Ltda."
    )
    return _send_email(
        to_email=to_email,
        subject="Tribultz Suporte — Ticket recebido",
        html_body=html_body,
        text_body=text_body,
        log_url=f"{settings.FRONTEND_URL}/support",
    )


def send_ticket_status_email(
    to_email: str,
    user_name: str,
    ticket_title: str,
    new_status: str,
) -> bool:
    """Notify user of a ticket status change."""
    status_labels = {
        "open": "Aberto",
        "in_progress": "Em andamento",
        "resolved": "Resolvido",
        "closed": "Encerrado",
    }
    status_display = status_labels.get(new_status, new_status)
    html_body = _render(
        "support_ticket_created.html",
        user_name=user_name,
        ticket_title=ticket_title,
        priority=f"Status atualizado para: {status_display}",
        console_url=f"{settings.FRONTEND_URL}/support",
        frontend_url=settings.FRONTEND_URL,
    )
    text_body = (
        f"Olá, {user_name}!\n\n"
        f"Seu ticket '{ticket_title}' foi atualizado para: {status_display}.\n\n"
        f"Acompanhe em: {settings.FRONTEND_URL}/support\n\n"
        "Tribultz Tecnologia Ltda."
    )
    return _send_email(
        to_email=to_email,
        subject=f"Tribultz Suporte — Ticket {status_display}",
        html_body=html_body,
        text_body=text_body,
        log_url=f"{settings.FRONTEND_URL}/support",
    )


def send_feedback_received_email(to_email: str, user_name: str) -> bool:
    """Send thank-you email after feedback submission."""
    html_body = _render(
        "feedback_received.html",
        user_name=user_name,
        console_url=f"{settings.FRONTEND_URL}/dashboard",
        frontend_url=settings.FRONTEND_URL,
    )
    text_body = (
        f"Olá, {user_name}!\n\n"
        "Recebemos seu feedback. Obrigado por ajudar a melhorar o Tribultz!\n\n"
        "Tribultz Tecnologia Ltda."
    )
    return _send_email(
        to_email=to_email,
        subject="Tribultz — Feedback recebido, obrigado!",
        html_body=html_body,
        text_body=text_body,
        log_url=f"{settings.FRONTEND_URL}/dashboard",
    )


def send_staff_ticket_notification(ticket_title: str, user_email: str, priority: str) -> bool:
    """Notify contato@tribultz.com.br when a new ticket is opened."""
    priority_labels = {"low": "Baixa", "medium": "Média", "high": "Alta", "critical": "Crítica"}
    text_body = (
        f"Novo ticket de suporte recebido.\n\n"
        f"Assunto: {ticket_title}\n"
        f"Usuário: {user_email}\n"
        f"Prioridade: {priority_labels.get(priority, priority)}\n\n"
        f"Acesse: {settings.FRONTEND_URL}/support"
    )
    return _send_email(
        to_email="contato@tribultz.com.br",
        subject=f"[Suporte] Novo ticket — {ticket_title}",
        html_body=f"<pre>{text_body}</pre>",
        text_body=text_body,
        log_url=f"{settings.FRONTEND_URL}/support",
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
