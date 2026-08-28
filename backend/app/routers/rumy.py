"""Rumy router — receptor do webhook de handoff (F2 Round 5; hardening #693).

Fluxo: limita leitura → autentica origem → amarra Event ID ao corpo assinado →
persiste bruto → enfileira worker. Validação de schema e domínio acontecem no
worker — nenhum evento autenticado se perde por payload inesperado.

Semântica de resposta — desvio DELIBERADO da convenção sempre-200 dos webhooks
Asaas/Attio deste repo: aqui o retry do produtor é desejado (at-least-once).
  404 — RUMY_WEBHOOK_ENABLED=false (default): endpoint inexistente p/ o mundo.
  503 — HANDOFF_TENANT_ID não configurado (fail-closed, sem efeito colateral).
  413 — corpo acima do teto aplicacional (recusado durante a leitura).
  400 — Event ID ausente/malformado, ou divergente do ``id`` do corpo assinado.
  401 — assinatura/carimbo ausente, inválido ou fora da janela de ±5 min.
        O motivo exato fica só no log: não ensinar ao atacante qual borda caiu.
  409 — mesmo Event ID com corpo diferente (conflito de integridade). Resposta
        deliberada em vez de 200: aceitar seria mentir, e descartar calado
        esconderia defeito do produtor. Custa 7 retries — todos com evidência.
  200 — aceito (accepted) ou reentrega idêntica (duplicate).
  5xx — falha transitória (ex.: banco fora): o produtor re-tenta e a camada de
        idempotência absorve a reentrega.

Nada é persistido antes de 401/413/400 passarem.
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
    is_valid_event_id,
    verify_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["rumy"])


async def _read_capped(request: Request, limit: int) -> bytes:
    """Lê o corpo em fluxo, abortando ao ultrapassar ``limit``.

    Não confia em ``Content-Length``: cliente hostil omite o header ou mente.
    O corte acontece durante a leitura — o processo nunca materializa mais que
    o teto, mesmo para requisição não autenticada. Autenticar exige o corpo
    inteiro, então este teto é a única proteção possível antes do HMAC.
    """
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail="corpo acima do limite")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/rumy", status_code=200)
async def rumy_webhook(request: Request, db: Session = Depends(get_db)):
    """Recebe eventos do Rumy. Flag OFF por padrão — sem superfície externa."""
    if not settings.RUMY_WEBHOOK_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")
    if not settings.HANDOFF_TENANT_ID:
        logger.error("rumy_webhook_misconfigured reason=handoff_tenant_id_ausente")
        raise HTTPException(status_code=503, detail="handoff não configurado")

    raw_body = await _read_capped(request, settings.RUMY_MAX_BODY_BYTES)

    signature = request.headers.get(SIGNATURE_HEADER, "")
    timestamp = request.headers.get(TIMESTAMP_HEADER, "")
    if not verify_signature(raw_body, signature, timestamp):
        logger.warning("rumy_webhook_rejected reason=invalid_signature")
        raise HTTPException(status_code=401, detail="assinatura inválida")

    provider_event_id = (request.headers.get(EVENT_ID_HEADER, "") or "").strip()
    event_type_raw = request.headers.get(EVENT_TYPE_HEADER, "")

    if not is_valid_event_id(provider_event_id):
        # Cobre ausente, vazio, CR/LF, controle e comprimento acima da coluna.
        # Rejeitar aqui é o que impede o header hostil de virar erro de banco.
        logger.warning("rumy_webhook_rejected reason=event_id_invalido bytes=%d",
                       len(provider_event_id))
        raise HTTPException(status_code=400, detail="X-Rumy-Event-Id inválido")

    try:
        parsed = json.loads(raw_body)
        if not isinstance(parsed, dict):
            parsed = {"_non_object_body": True, "body": parsed}
    except (json.JSONDecodeError, UnicodeDecodeError):
        parsed = None  # persist_raw_event preserva por hash (bug do produtor)

    # Binding: a assinatura cobre {timestamp}.{corpo}, NÃO os headers. Sem esta
    # amarra, uma requisição legítima capturada pode ser reenviada trocando só
    # o Event ID e inflar o ledger indefinidamente dentro da janela de 300s.
    if parsed is not None and "id" in parsed:
        if str(parsed.get("id")) != provider_event_id:
            logger.warning("rumy_webhook_rejected reason=event_id_divergente_do_corpo")
            raise HTTPException(status_code=400, detail="Event ID divergente do corpo")

    tenant_id = uuid.UUID(settings.HANDOFF_TENANT_ID)
    row, created, outcome = persist_raw_event(
        db, tenant_id, raw_body, parsed, provider_event_id=provider_event_id
    )
    db.commit()

    if outcome == "integrity_conflict":
        logger.warning(
            "rumy_webhook_integrity_conflict ledger=%s event_id=%s", row.id, provider_event_id
        )
        raise HTTPException(status_code=409, detail="Event ID já visto com corpo diferente")

    if created:
        # Enfileira após o commit — broker fora deixa a linha 'received' no
        # ledger, reprocessável. Nada se perde.
        try:
            from app.tasks.task_k_rumy import process_rumy_event

            process_rumy_event.delay(str(row.id))
        except Exception:  # noqa: BLE001 — broker fora não derruba o recebimento
            logger.exception("rumy_webhook_enqueue_failed ledger=%s (linha fica 'received')", row.id)

    logger.info(
        "rumy_webhook_received ledger=%s outcome=%s event_id=%s type=%s",
        row.id, outcome, provider_event_id, event_type_raw or "(ausente)",
    )
    return {"status": "accepted" if created else "duplicate", "event": str(row.id)}
