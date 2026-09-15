"""Callback mínimo do piloto CBS v2; desligado por quatro gates cumulativos."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.cbs_v2_pilot import (
    get_sync_run_by_callback,
    ingest_external_payload,
    pilot_is_active,
)

router = APIRouter(prefix="/api/v1/webhooks/cbs-v2", tags=["cbs-v2-pilot"])


async def _read_capped(request: Request, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail="corpo acima do limite")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/{callback_id}", status_code=202)
async def receive_cbs_v2_callback(
    callback_id: UUID, request: Request, db: Session = Depends(get_db)
):
    if not pilot_is_active():
        raise HTTPException(status_code=404, detail="Not Found")
    run = get_sync_run_by_callback(db, callback_id=callback_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Not Found")

    raw_body = await _read_capped(request, settings.CBS_V2_MAX_WEBHOOK_BODY_BYTES)
    try:
        ingested = ingest_external_payload(
            db,
            run=run,
            raw_body=raw_body,
            source="WEBHOOK",
            content_type=request.headers.get("content-type", "application/octet-stream"),
        )
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        # Nem payload, URL assinada, credenciais ou identificadores de tenant
        # entram no log/erro HTTP desta fronteira externa.
        raise HTTPException(status_code=503, detail="evidência não persistida") from None

    return {
        "status": "accepted" if ingested.created else "duplicate",
        "state": ingested.event.state,
        "result": ingested.event.result,
    }
