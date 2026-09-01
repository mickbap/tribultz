"""Persistência e aplicação dos webhooks Resend relevantes ao Growth P0."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.prospect_suppression import ProspectSuppression
from app.models.resend_webhook_event import ResendWebhookEvent
from app.services.growth.resend_p0 import normalize_email


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _event_emails(event_type: str, data: dict[str, Any]) -> list[str]:
    if event_type == "contact.updated":
        candidates = [data.get("email")]
    elif event_type == "suppression.added":
        candidates = [data.get("email")]
    elif event_type == "email.bounced":
        raw_to = data.get("to")
        candidates = raw_to if isinstance(raw_to, list) else []
    else:
        candidates = []
    normalized = [normalize_email(value) for value in candidates if isinstance(value, str)]
    return list(dict.fromkeys(email for email in normalized if email))


def _suppression_status(event_type: str, data: dict[str, Any]) -> str | None:
    if event_type == "contact.updated" and data.get("unsubscribed") is True:
        return "opt_out"
    if event_type == "email.bounced":
        bounce = data.get("bounce")
        if isinstance(bounce, dict) and str(bounce.get("type", "")).lower() == "permanent":
            return "hard_bounce"
    if event_type == "suppression.added" and data.get("origin") == "bounce":
        return "hard_bounce"
    return None


def persist_and_apply_resend_event(
    db: Session, *, svix_id: str, payload: dict[str, Any]
) -> tuple[ResendWebhookEvent, bool]:
    """Persiste evento uma vez e aplica apenas bloqueios; nunca remove suppression."""
    existing = db.execute(
        select(ResendWebhookEvent).where(ResendWebhookEvent.svix_id == svix_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    event_type = str(payload.get("type") or "unknown")[:64]
    data = payload.get("data")
    data = data if isinstance(data, dict) else {}
    emails = _event_emails(event_type, data)
    occurred_at = _parse_timestamp(payload.get("created_at"))
    row = ResendWebhookEvent(
        svix_id=svix_id,
        event_type=event_type,
        occurred_at=occurred_at,
        email_id=str(data.get("email_id"))[:128] if data.get("email_id") else None,
        recipient_email=emails[0] if emails else None,
        payload_raw=payload,
        status="received",
    )
    db.add(row)
    db.flush()

    status = _suppression_status(event_type, data)
    if status is None or not emails:
        row.status = "ignored"  # type: ignore[assignment]
        row.applied_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        return row, True

    reason = "unsubscribe_resend" if status == "opt_out" else "hard_bounce_resend"
    for email in emails:
        already_suppressed = db.execute(
            select(ProspectSuppression.id).where(
                ProspectSuppression.email == email,
                ProspectSuppression.status == status,
            )
        ).scalar_one_or_none()
        if already_suppressed is None:
            db.add(
                ProspectSuppression(
                    email=email,
                    status=status,
                    reason=reason,
                    source="resend",
                    source_event_id=svix_id,
                    occurred_at=occurred_at,
                )
            )
    row.status = "applied"  # type: ignore[assignment]
    row.applied_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    return row, True
