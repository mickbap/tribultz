"""Inbox do webhook Rumy — persistência bruta + processamento assíncrono (F2, Round 5).

Duas camadas de idempotência, deliberadamente distintas:

1. Transporte (este módulo): dedupe de reentregas byte-idênticas pela chave
   ``raw:<sha256(corpo)>`` — o corpo é persistido ANTES de qualquer validação
   de schema, então nenhum evento autenticado se perde, nem quando o payload
   surpreende (Round 3 A1: persistir bruto vem antes de validar).
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
) -> tuple[CrmLeadEvent, bool]:
    """Grava o corpo bruto no ledger (camada de transporte). Retorna (linha, criada?).

    Reentrega byte-idêntica incrementa ``attempts`` na linha existente (dedupe
    de transporte). Corpo não-JSON é preservado por hash — autenticado, então é
    evidência de bug do produtor, não lixo a descartar.
    """
    body_sha = hashlib.sha256(raw_body).hexdigest()
    key = f"raw:{body_sha}"
    existing = (
        session.query(CrmLeadEvent).filter(CrmLeadEvent.idempotency_key == key).one_or_none()
    )
    if existing is not None:
        existing.attempts = (existing.attempts or 1) + 1
        return existing, False

    row = CrmLeadEvent(
        tenant_id=tenant_id,
        source_system=source_system,
        external_lead_id=RAW_PENDING,
        idempotency_key=key,
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
        row.processing_result = {"detail": "shadow_mode"}
        session.flush()
        return {"detail": "shadow_mode", "status": row.status}

    adapter = adapter or get_adapter()
    row.adapter_version = adapter.version
    ts = now or datetime.now(timezone.utc)

    try:
        outcome = adapter.to_handoff_event(row.payload_raw or {})
    except (ValidationError, ValueError, TypeError) as exc:
        # Payload sem campos obrigatórios / malformado: quarentena (fila humana).
        row.status = "quarantined"
        row.error = str(exc)[:2000]
        row.processing_result = {"detail": "adapter_contract_error"}
        session.flush()
        return {"detail": "adapter_contract_error", "status": "quarantined"}
    except Exception as exc:  # noqa: BLE001 — fronteira do worker: marcar e re-tentar
        row.status = "failed"
        row.error = str(exc)[:2000]
        session.flush()
        raise ProcessingError(f"adapter falhou: {exc}") from exc

    if isinstance(outcome, UnmappedEvent):
        row.status = "unmapped"
        row.event_type_raw = outcome.event_type_raw[:128]
        row.processing_result = {"detail": "unmapped", "note": outcome.note}
        session.flush()
        return {"detail": "unmapped", "status": "unmapped"}

    event = outcome
    result = ingest_handoff_event(
        session,
        row.tenant_id,
        event,
        payload_raw=row.payload_raw,
        provider_event_id=event.event_id,
        adapter_version=adapter.version,
        now=ts,
    )

    # A linha bruta espelha o desfecho de negócio e aponta para a linha canônica.
    row.external_lead_id = event.external_lead_id
    row.event_type = event.event_type
    row.event_type_raw = RAW_EVENT_TYPE
    row.occurred_at = event.occurred_at
    row.occurred_at_source = "provider"
    row.status = result.status
    if result.status == "applied":
        row.applied_at = ts
    row.processing_result = {
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
