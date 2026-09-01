"""Webhook autenticado do Resend para suppression canônica (#733)."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from svix.webhooks import Webhook, WebhookVerificationError

from app.config import settings
from app.database import get_db
from app.services.growth.resend_webhook import persist_and_apply_resend_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/webhooks", tags=["resend"])


async def _read_capped(request: Request, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail="corpo acima do limite")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/resend", status_code=200)
async def resend_webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.RESEND_WEBHOOK_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")
    if not settings.RESEND_WEBHOOK_SECRET:
        logger.error("resend_webhook_misconfigured reason=secret_ausente")
        raise HTTPException(status_code=503, detail="webhook não configurado")

    raw_body = await _read_capped(request, settings.RESEND_MAX_BODY_BYTES)
    try:
        Webhook(settings.RESEND_WEBHOOK_SECRET).verify(raw_body, dict(request.headers))
    except WebhookVerificationError:
        logger.warning("resend_webhook_rejected reason=invalid_signature")
        raise HTTPException(status_code=401, detail="assinatura inválida") from None
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="payload inválido") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload inválido")

    svix_id = (request.headers.get("svix-id") or "").strip()
    if not svix_id or len(svix_id) > 128:
        raise HTTPException(status_code=400, detail="svix-id inválido")
    try:
        event, created = persist_and_apply_resend_event(
            db, svix_id=svix_id, payload=payload
        )
        db.commit()
    except IntegrityError:
        # Entregas concorrentes do mesmo svix-id disputam a UNIQUE. Uma delas
        # já aplicou (ou aplicará) o evento; responder 200 evita efeitos duplos.
        db.rollback()
        return {"status": "duplicate", "svix_id": svix_id}
    return {
        "status": event.status if created else "duplicate",
        "svix_id": svix_id,
    }
