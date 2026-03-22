"""Cloudflare Turnstile CAPTCHA verification.

When CAPTCHA_ENABLED=false (default in dev), validation is skipped.
When enabled, the frontend sends a captcha_token from the Turnstile widget
and this service validates it via Cloudflare's siteverify endpoint.

Test keys (always pass):
  Site key:   1x00000000000000000000AA
  Secret key: 1x0000000000000000000000000000000AA
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_captcha(token: str, remote_ip: str | None = None) -> bool:
    """Verify a Turnstile token. Returns True if valid or CAPTCHA is disabled."""
    if not settings.CAPTCHA_ENABLED:
        return True

    if not settings.TURNSTILE_SECRET_KEY:
        logger.warning("captcha_no_secret_key: CAPTCHA_ENABLED but no TURNSTILE_SECRET_KEY set")
        return True

    if not token:
        return False

    try:
        payload: dict[str, str] = {
            "secret": settings.TURNSTILE_SECRET_KEY,
            "response": token,
        }
        if remote_ip:
            payload["remoteip"] = remote_ip

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(SITEVERIFY_URL, data=payload)
            data = resp.json()
            success = bool(data.get("success", False))
            if not success:
                codes = data.get("error-codes", [])
                logger.warning("captcha_failed", extra={"errors": codes})
            return success
    except Exception as exc:
        logger.error("captcha_verify_error", extra={"error": str(exc)})
        # Fail open: don't block users if Cloudflare is unreachable
        return True
