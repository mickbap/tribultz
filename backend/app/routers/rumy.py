"""Rumy router — receptor do webhook de handoff (F2, Round 5 da PO-2026-07-CRM-001).

Fluxo (Round 3 §2): autentica origem → persiste bruto → enfileira worker.
Validação de schema e domínio acontecem no worker (inbox.process_raw_event) —
nenhum evento autenticado se perde por payload inesperado.

Semântica de resposta — desvio DELIBERADO da convenção sempre-200 dos webhooks
Asaas/Attio deste repo: aqui o retry do produtor é desejado (at-least-once).
  404 — RUMY_WEBHOOK_ENABLED=false (default): endpoint inexistente p/ o mundo.
  503 — HANDOFF_TENANT_ID não configurado (fail-closed, sem efeito colateral).
  401 — assinatura/carimbo ausente, inválido ou fora da janela de ±5 min
        (nada é persistido; o motivo exato fica só no log).
  200 — aceito (accepted) ou reentrega byte-idêntica (duplicate).
  5xx — falha transitória (ex.: banco fora): o produtor re-tenta e a camada de
        idempotência absorve a reentrega.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.handoff.inbox import persist_raw_event
from app.services.handoff.webhook_auth import (
    EVENT_ID_HEADER,
    EVENT_TYPE_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    verify_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["rumy"])


@router.post("/rumy", status_code=200)
async def rumy_webhook(request: Request, db: Session = Depends(get_db)):
    """Recebe eventos do Rumy. Flag OFF por padrão — sem superfície externa."""
    if not settings.RUMY_WEBHOOK_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")
    if not settings.HANDOFF_TENANT_ID:
        logger.error("rumy_webhook_misconfigured reason=handoff_tenant_id_ausente")
        raise HTTPException(status_code=503, detail="handoff não configurado")

    raw_body = await request.body()
    signature = request.headers.get(SIGNATURE_HEADER, "")
    timestamp = request.headers.get(TIMESTAMP_HEADER, "")
    if not verify_signature(raw_body, signature, timestamp):
        # Motivo específico fica no log; ao cliente vai só 401 (não ensinar o
        # atacante qual borda ele cruzou).
        logger.warning("rumy_webhook_rejected reason=invalid_signature")
        raise HTTPException(status_code=401, detail="assinatura inválida")

    provider_event_id = request.headers.get(EVENT_ID_HEADER, "")
    event_type_raw = request.headers.get(EVENT_TYPE_HEADER, "")

    try:
        parsed = json.loads(raw_body)
        if not isinstance(parsed, dict):
            parsed = {"_non_object_body": True, "body": parsed}
    except (json.JSONDecodeError, UnicodeDecodeError):
        parsed = None  # persist_raw_event preserva por hash (evidência de bug do produtor)

    tenant_id = uuid.UUID(settings.HANDOFF_TENANT_ID)
    row, created = persist_raw_event(
        db, tenant_id, raw_body, parsed, provider_event_id=provider_event_id
    )
    db.commit()

    if created:
        # Enfileira após o commit — se o broker estiver fora, a linha fica
        # 'received' no ledger e é reprocessável (nada se perde).
        try:
            from app.tasks.task_k_rumy import process_rumy_event

            process_rumy_event.delay(str(row.id))
        except Exception:  # noqa: BLE001 — broker fora não pode derrubar o recebimento
            logger.exception("rumy_webhook_enqueue_failed ledger=%s (linha fica 'received')", row.id)

    logger.info(
        "rumy_webhook_received ledger=%s created=%s event_id=%s type=%s",
        row.id, created, provider_event_id or "(ausente)", event_type_raw or "(ausente)",
    )
    return {"status": "accepted" if created else "duplicate", "event": str(row.id)}
