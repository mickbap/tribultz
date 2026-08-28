"""Inbox do webhook Rumy — persistência bruta + processamento assíncrono (F2, Round 5).

Duas camadas de idempotência, deliberadamente distintas:

1. Transporte (este módulo): dedupe pela identidade que o produtor garante —
   ``evt:<X-Rumy-Event-Id>``. O Rumy re-tenta até 7× com o MESMO Event ID, mas
   NÃO garante os mesmos bytes: qualquer reserialização (ordem de chaves,
   espaçamento, ``api_version``) mudaria um hash de corpo e deixaria o mesmo
   evento lógico entrar duas vezes (#689). O hash do corpo continua gravado
   como EVIDÊNCIA (``payload_hash``), não como chave. Sem Event ID — produtor
   fora do contrato — cai no hash, que é melhor que nada. O corpo é persistido
   ANTES de qualquer validação de schema, então nenhum evento autenticado se
   perde (Round 3 A1: persistir bruto vem antes de validar).
2. Negócio (service.py, F3): a chave do evento normalizado — o mesmo evento
   lógico reentregue com bytes diferentes morre lá.

O worker roda o adapter vigente (hoje: envelope interno; o adapter Rumy
definitivo está bloqueado até payload real) e entrega ao domínio via
``ingest_handoff_event``. Com ``HANDOFF_APPLY_ENABLED`` OFF o worker opera em
shadow mode: o evento fica no ledger, nada é aplicado (flag OFF nunca aplica;
flag OFF também nunca re-permite outbound — a proteção é do domínio).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.crm_handoff import CrmLeadEvent
from app.services.handoff.adapter import RumyAdapter, UnmappedEvent, get_adapter
from app.services.handoff.service import ingest_handoff_event

logger = logging.getLogger(__name__)

#: sentinela para colunas NOT NULL antes de o adapter identificar o lead —
#: nunca vaza para o domínio (o vínculo nasce só no ingest com o id real)
RAW_PENDING = "(raw)"
RAW_EVENT_TYPE = "provider.raw"


class ProcessingError(Exception):
    """Falha transitória de processamento — o worker deve re-tentar."""


def persist_raw_event(
    session: Session,
    tenant_id: uuid.UUID,
    raw_body: bytes,
    parsed: Optional[dict[str, Any]],
    source_system: str = "rumy",
    provider_event_id: Optional[str] = None,
) -> tuple[CrmLeadEvent, bool]:
    """Grava o corpo bruto no ledger (camada de transporte). Retorna (linha, criada?).

    Reentrega incrementa ``attempts`` na linha existente. Quando o mesmo Event
    ID chega com bytes diferentes, vence o PRIMEIRO corpo: ``payload_raw`` e
    ``payload_hash`` não são sobrescritos — reescrever apagaria a evidência do
    que foi autenticado primeiro. A divergência é registrada em log.

    Corpo não-JSON é preservado por hash — autenticado, então é evidência de bug
    do produtor, não lixo a descartar.
    """
    body_sha = hashlib.sha256(raw_body).hexdigest()
    evt_id = (provider_event_id or "").strip()
    key = f"evt:{evt_id}" if evt_id else f"raw:{body_sha}"
    existing = (
        session.query(CrmLeadEvent).filter(CrmLeadEvent.idempotency_key == key).one_or_none()
    )
    if existing is not None:
        existing.attempts = (existing.attempts or 1) + 1  # type: ignore[assignment]
        if existing.payload_hash != body_sha:
            # Mesmo evento lógico, bytes diferentes. Idempotência preservada; a
            # divergência é anomalia do produtor e precisa ser visível.
            logger.warning(
                "rumy_event_id_body_divergence event_id=%s ledger=%s hash_gravado=%s hash_recebido=%s",
                evt_id or "(sem-id)", existing.id, existing.payload_hash, body_sha,
            )
        return existing, False

    row = CrmLeadEvent(
        tenant_id=tenant_id,
        source_system=source_system,
        external_lead_id=RAW_PENDING,
        idempotency_key=key,
        provider_event_id=evt_id or None,
        schema_version="raw",
        event_type=RAW_EVENT_TYPE,
        occurred_at=None,
        occurred_at_source="received",
        payload_raw=parsed
        if parsed is not None
        else {"_non_json_body": True, "sha256": body_sha, "bytes": len(raw_body)},
        payload_hash=body_sha,
        status="received",
    )
    session.add(row)
    session.flush()
    return row, True


def process_raw_event(
    session: Session,
    ledger_id: uuid.UUID,
    adapter: Optional[RumyAdapter] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Processa uma linha bruta: adapter → contrato interno → domínio.

    Idempotente: linha já processada é no-op. Erros de contrato quarentenam
    (retry não conserta payload); erros inesperados marcam ``failed`` e
    levantam ProcessingError para o retry do worker.
    """
    row = session.get(CrmLeadEvent, ledger_id)
    if row is None:
        raise ProcessingError(f"ledger {ledger_id} não encontrado")
    if row.status not in ("received", "failed"):
        return {"detail": "already_processed", "status": row.status}

    if not settings.HANDOFF_APPLY_ENABLED:
        # Shadow mode: evento persiste, nada é aplicado. Flag OFF nunca aplica.
        row.processing_result = {"detail": "shadow_mode"}  # type: ignore[assignment]
        session.flush()
        return {"detail": "shadow_mode", "status": row.status}

    adapter = adapter or get_adapter()
    row.adapter_version = adapter.version  # type: ignore[assignment]
    ts = now or datetime.now(timezone.utc)

    try:
        outcome = adapter.to_handoff_event(row.payload_raw or {})  # type: ignore[arg-type]
    except (ValidationError, ValueError, TypeError) as exc:
        # Payload sem campos obrigatórios / malformado: quarentena (fila humana).
        row.status = "quarantined"  # type: ignore[assignment]
        row.error = str(exc)[:2000]  # type: ignore[assignment]
        row.processing_result = {"detail": "adapter_contract_error"}  # type: ignore[assignment]
        session.flush()
        return {"detail": "adapter_contract_error", "status": "quarantined"}
    except Exception as exc:  # noqa: BLE001 — fronteira do worker: marcar e re-tentar
        row.status = "failed"  # type: ignore[assignment]
        row.error = str(exc)[:2000]  # type: ignore[assignment]
        session.flush()
        raise ProcessingError(f"adapter falhou: {exc}") from exc

    if isinstance(outcome, UnmappedEvent):
        row.status = "unmapped"  # type: ignore[assignment]
        row.event_type_raw = outcome.event_type_raw[:128]  # type: ignore[assignment]
        row.processing_result = {"detail": "unmapped", "note": outcome.note}  # type: ignore[assignment]
        session.flush()
        return {"detail": "unmapped", "status": "unmapped"}

    event = outcome
    result = ingest_handoff_event(
        session,
        row.tenant_id,  # type: ignore[arg-type]
        event,
        payload_raw=row.payload_raw,  # type: ignore[arg-type]
        provider_event_id=event.event_id,
        adapter_version=adapter.version,
        now=ts,
    )

    # A linha bruta espelha o desfecho de negócio e aponta para a linha canônica.
    row.external_lead_id = event.external_lead_id  # type: ignore[assignment]
    row.event_type = event.event_type  # type: ignore[assignment]
    row.event_type_raw = RAW_EVENT_TYPE  # type: ignore[assignment]
    row.occurred_at = event.occurred_at  # type: ignore[assignment]
    row.occurred_at_source = "provider"  # type: ignore[assignment]
    row.status = result.status  # type: ignore[assignment]
    if result.status == "applied":
        row.applied_at = ts  # type: ignore[assignment]
    row.processing_result = {  # type: ignore[assignment]
        "detail": result.detail,
        "business_ledger_id": str(result.ledger.id),
    }
    session.flush()
    logger.info(
        "rumy_inbox_processed ledger=%s status=%s detail=%s", row.id, result.status, result.detail
    )
    return {
        "detail": result.detail,
        "status": result.status,
        "business_ledger_id": str(result.ledger.id),
    }
