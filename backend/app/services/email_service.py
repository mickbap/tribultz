"""Email service — SMTP sending with graceful degradation.

When EMAIL_VERIFICATION_ENABLED=False (default for dev), emails are
logged to stdout instead of sent via SMTP.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def send_verification_email(to_email: str, user_name: str, token: str) -> bool:
    """Send email verification link. Returns True on success."""
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"

    subject = "Tribultz — Confirme seu email"
    html_body = f"""\
<html>
<body style="font-family: sans-serif; color: #1e293b; max-width: 560px; margin: 0 auto;">
  <h2 style="color: #1d4ed8;">Tribultz</h2>
  <p>Olá, <strong>{user_name}</strong>!</p>
  <p>Obrigado por se cadastrar no Tribultz Console. Para ativar sua conta,
     confirme seu email clicando no botão abaixo:</p>
  <p style="text-align: center; margin: 24px 0;">
    <a href="{verify_url}"
       style="background: #2563eb; color: white; padding: 12px 28px;
              border-radius: 8px; text-decoration: none; font-weight: 600;">
      Confirmar email
    </a>
  </p>
  <p style="font-size: 13px; color: #64748b;">
    Ou copie e cole este link no navegador:<br/>
    <a href="{verify_url}">{verify_url}</a>
  </p>
  <p style="font-size: 13px; color: #64748b;">
    Este link expira em 24 horas. Se você não solicitou este cadastro,
    ignore este email.
  </p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;"/>
  <p style="font-size: 11px; color: #94a3b8;">
    Tribultz Tecnologia Ltda. — Conformidade tributária em tempo de execução.<br/>
    DPO: dpo@tribultz.com.br
  </p>
</body>
</html>"""

    text_body = (
        f"Olá, {user_name}!\n\n"
        f"Confirme seu email acessando: {verify_url}\n\n"
        "Este link expira em 24 horas.\n"
        "Tribultz Tecnologia Ltda."
    )

    return _send_email(to_email, subject, html_body, text_body, verify_url)


def send_password_reset_email(to_email: str, user_name: str, token: str) -> bool:
    """Send password reset link. Returns True on success."""
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    subject = "Tribultz — Redefinir senha"
    html_body = f"""\
<html>
<body style="font-family: sans-serif; color: #1e293b; max-width: 560px; margin: 0 auto;">
  <h2 style="color: #1d4ed8;">Tribultz</h2>
  <p>Olá, <strong>{user_name}</strong>!</p>
  <p>Recebemos uma solicitação para redefinir a senha da sua conta no Tribultz Console.
     Clique no botão abaixo para criar uma nova senha:</p>
  <p style="text-align: center; margin: 24px 0;">
    <a href="{reset_url}"
       style="background: #2563eb; color: white; padding: 12px 28px;
              border-radius: 8px; text-decoration: none; font-weight: 600;">
      Redefinir senha
    </a>
  </p>
  <p style="font-size: 13px; color: #64748b;">
    Ou copie e cole este link no navegador:<br/>
    <a href="{reset_url}">{reset_url}</a>
  </p>
  <p style="font-size: 13px; color: #64748b;">
    Este link expira em 1 hora. Se você não solicitou a redefinição,
    ignore este email — sua senha permanece inalterada.
  </p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;"/>
  <p style="font-size: 11px; color: #94a3b8;">
    Tribultz Tecnologia Ltda. — Conformidade tributária em tempo de execução.<br/>
    DPO: dpo@tribultz.com.br
  </p>
</body>
</html>"""

    text_body = (
        f"Olá, {user_name}!\n\n"
        f"Redefina sua senha acessando: {reset_url}\n\n"
        "Este link expira em 1 hora.\n"
        "Se você não solicitou, ignore este email.\n"
        "Tribultz Tecnologia Ltda."
    )

    return _send_email(to_email, subject, html_body, text_body, reset_url)


def _send_email(to_email: str, subject: str, html_body: str, text_body: str, log_url: str) -> bool:
    """Internal: send or log an email."""
    if not settings.EMAIL_VERIFICATION_ENABLED or not settings.SMTP_HOST:
        logger.info(
            "email_logged (SMTP disabled)",
            extra={"to": to_email, "url": log_url},
        )
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        if settings.SMTP_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)

        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

        server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()

        logger.info("email_sent", extra={"to": to_email, "subject": subject})
        return True
    except Exception:
        logger.exception("email_send_failed", extra={"to": to_email, "subject": subject})
        return False
