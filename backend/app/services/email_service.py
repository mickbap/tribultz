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
  <p>Ola, <strong>{user_name}</strong>!</p>
  <p>Obrigado por se cadastrar no Tribultz Console. Para ativar sua conta,
     confirme seu email clicando no botao abaixo:</p>
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
    Este link expira em 24 horas. Se voce nao solicitou este cadastro,
    ignore este email.
  </p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;"/>
  <p style="font-size: 11px; color: #94a3b8;">
    Tribultz Tecnologia Ltda. — Conformidade tributaria em tempo de execucao.<br/>
    DPO: dpo@tribultz.com.br
  </p>
</body>
</html>"""

    text_body = (
        f"Ola, {user_name}!\n\n"
        f"Confirme seu email acessando: {verify_url}\n\n"
        "Este link expira em 24 horas.\n"
        "Tribultz Tecnologia Ltda."
    )

    if not settings.EMAIL_VERIFICATION_ENABLED or not settings.SMTP_HOST:
        logger.info(
            "email_verification_logged (SMTP disabled)",
            extra={"to": to_email, "verify_url": verify_url},
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

        logger.info("email_verification_sent", extra={"to": to_email})
        return True
    except Exception:
        logger.exception("email_verification_failed", extra={"to": to_email})
        return False
