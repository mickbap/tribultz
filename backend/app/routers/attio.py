"""Attio router — inbound webhooks from Attio CRM.

PO-2026-07-CRM-001, fatia 7/12. Scope boundary: this fatia covers receiving
and verifying webhook signatures only. Per-event-type business reactions
(e.g. "empresa criada no Attio -> atualizar X no Tribultz") are
deliberately not implemented here — they depend on product decisions about
what each event should trigger, which don't exist yet. Add them as
concrete requirements land.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.integrations.attio.webhooks import verify_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["attio"])


@router.post("/attio", status_code=200)
async def attio_webhook(request: Request):
    """Receive Attio CRM events.

    Always returns 200 to prevent retries (same convention as the Asaas
    webhook in billing.py) — an invalid signature is logged and ignored
    rather than surfaced as an error to the caller.
    """
    raw_body = await request.body()
    signature = request.headers.get("attio-signature") or request.headers.get(
        "x-attio-signature", ""
    )

    if not verify_signature(raw_body, signature):
        logger.warning("attio_webhook_rejected reason=invalid_signature")
        return {"status": "ignored", "reason": "invalid signature"}

    payload = await request.json()
    # A doc pública do Attio não deixa claro se o corpo é um único evento ou
    # um array em "events" — trata os dois formatos defensivamente até
    # confirmarmos contra um workspace real.
    events = payload.get("events", [payload]) if isinstance(payload, dict) else [payload]

    for event in events:
        event_type = event.get("event_type", "unknown") if isinstance(event, dict) else "unknown"
        logger.info("attio_webhook_received event_type=%s", event_type)

    return {"status": "ok", "events_received": len(events)}
