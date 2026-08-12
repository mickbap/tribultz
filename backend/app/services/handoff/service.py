"""Ingestão idempotente de eventos de handoff — F3 do Round 4.

Pipeline interno (camadas 1–3 do kill switch do Round 3 §15): ledger →
idempotência → identidade (DEC-5) → vínculo → transição de ownership com trava
local. As camadas 4–5 (comando/confirmação de supressão no Rumy) e a
orquestração do Attio NÃO existem nesta fatia — não autorizadas.

Garantias (Round 4 §6): o mesmo evento N vezes ⇒ 1 handoff lógico, 1 transição,
zero duplicação de pessoa, zero Deal (não existe código de Deal aqui — nasce
apenas por ato humano em Qualificado), zero histórico duplicado.

Sem efeito externo: nenhum router/task chama este módulo em runtime; o fio até
o endpoint (F2) chega em fatia futura atrás de RUMY_WEBHOOK_ENABLED /
HANDOFF_APPLY_ENABLED (OFF por padrão).
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.crm_handoff import CrmLeadEvent, CrmLeadLink
from app.services.handoff.contract import HandoffEvent
from app.services.handoff.identity import resolve_person
from app.services.handoff.ownership import (
    ActorType,
    OwnershipState,
    transition_ownership,
)

logger = logging.getLogger(__name__)

PROTECTED = {OwnershipState.HANDOFF_REQUESTED.value, OwnershipState.HUMAN_OWNED.value}


def canonical_payload_hash(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def compute_idempotency_key(
    tenant_id: uuid.UUID, event: HandoffEvent, provider_event_id: Optional[str] = None
) -> str:
    """Hierarquia do Round 3 A5: id do provedor > hash determinístico de negócio."""
    if provider_event_id:
        return f"prov:{event.source_system}:{provider_event_id}"[:128]
    basis = "|".join(
        [
            str(tenant_id),
            event.source_system,
            event.external_lead_id,
            event.event_type,
            event.occurred_at.isoformat(),
        ]
    )
    return "det:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()


@dataclass
class IngestResult:
    status: str  # applied | duplicate | quarantined | superseded
    ledger: CrmLeadEvent
    link: Optional[CrmLeadLink] = None
    detail: str = ""


def ingest_handoff_event(
    session: Session,
    tenant_id: uuid.UUID,
    event: HandoffEvent,
    payload_raw: Optional[dict[str, Any]] = None,
    provider_event_id: Optional[str] = None,
    adapter_version: Optional[str] = None,
    now: Optional[datetime] = None,
) -> IngestResult:
    """Processa um HandoffEvent de ponta a ponta, com idempotência perpétua."""
    ts = now or datetime.now(timezone.utc)
    normalized = event.model_dump(mode="json")
    p_hash = canonical_payload_hash(payload_raw if payload_raw is not None else normalized)
    key = compute_idempotency_key(tenant_id, event, provider_event_id)

    existing = (
        session.query(CrmLeadEvent).filter(CrmLeadEvent.idempotency_key == key).one_or_none()
    )
    if existing is not None:
        return _register_duplicate(session, existing, p_hash)

    ledger = CrmLeadEvent(
        tenant_id=tenant_id,
        source_system=event.source_system,
        external_lead_id=event.external_lead_id,
        idempotency_key=key,
        provider_event_id=provider_event_id,
        schema_version=event.schema_version,
        adapter_version=adapter_version,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        occurred_at_source="provider",
        payload_raw=payload_raw,
        payload_normalized=normalized,
        payload_hash=p_hash,
        status="received",
    )
    session.add(ledger)
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError:
        # Corrida entre consumidores: outro venceu o UNIQUE — vira duplicado.
        session.expunge(ledger)
        winner = (
            session.query(CrmLeadEvent).filter(CrmLeadEvent.idempotency_key == key).one()
        )
        return _register_duplicate(session, winner, p_hash)

    # Quarentena: mínimo de identidade ausente ⇒ fila de exceção humana,
    # nada fabricado, nada escrito além do ledger (Round 2 D-2, Round 4 §3).
    if not event.has_identity_minimum:
        ledger.status = "quarantined"  # type: ignore[assignment]
        ledger.processing_result = {"detail": "identity_minimum_missing"}  # type: ignore[assignment]
        return IngestResult(status="quarantined", ledger=ledger, detail="identity_minimum_missing")

    resolution = resolve_person(
        session,
        tenant_id,
        event.person.email.value if event.person.email.is_known else None,
        event.person.linkedin_url.value if event.person.linkedin_url.is_known else None,
        display_name=event.person.full_name,
    )

    link = (
        session.query(CrmLeadLink)
        .filter(
            CrmLeadLink.tenant_id == tenant_id,
            CrmLeadLink.source_system == event.source_system,
            CrmLeadLink.external_lead_id == event.external_lead_id,
        )
        .one_or_none()
    )
    if link is None:
        link = CrmLeadLink(
            tenant_id=tenant_id,
            source_system=event.source_system,
            external_lead_id=event.external_lead_id,
            ownership_state=OwnershipState.AUTOMATED.value,
            automation_state="ACTIVE",
            provider_ids={"provider_event_id": provider_event_id} if provider_event_id else {},
        )
        session.add(link)
        session.flush()

    if resolution.conflict:
        # Fail-safe DEC-5: sem merge; conflito bloqueia outbound até curadoria.
        link.identity_conflict = True  # type: ignore[assignment]
    elif resolution.identity is not None and link.person_identity_id is None:
        link.person_identity_id = resolution.identity.id

    # Fora de ordem (Round 3 A7): evento mais velho nunca regride estado.
    if link.last_occurred_at is not None and event.occurred_at <= link.last_occurred_at:  # type: ignore[misc]
        ledger.status = "superseded"  # type: ignore[assignment]
        ledger.processing_result = {  # type: ignore[assignment]
            "detail": "out_of_order",
            "last_occurred_at": link.last_occurred_at.isoformat(),
        }
        return IngestResult(status="superseded", ledger=ledger, link=link, detail="out_of_order")

    current = link.ownership_state
    if current in (OwnershipState.AUTOMATED.value, OwnershipState.RELEASED.value):
        transition_ownership(
            session,
            link,
            OwnershipState.HANDOFF_REQUESTED,
            ActorType.PROVIDER_EVENT,
            actor_ref=event.producer,
            reason=f"handoff.requested ({event.reason})",
            event_id=ledger.id,  # type: ignore[arg-type]
            now=ts,
        )
        detail = "transitioned"
        # Caminho C (Round 7 §7): alerta operacional de pausa — best-effort e
        # idempotente por ciclo; falha de alerta jamais derruba o ingest.
        try:
            from app.services.handoff.alerts import raise_pause_alert

            alert = raise_pause_alert(
                session, link,
                person_display=event.person.full_name,
                campaign=event.campaign_id or "",
                now=ts,
            )
        except Exception:  # noqa: BLE001
            logger.exception("handoff_alert_failed link=%s", link.id)
            alert = {"raised": False, "detail": "alert_error"}
    elif current in PROTECTED:
        # Pessoa/lead já sob atenção: evento é real e fica registrado; estado
        # não muda (idempotência lógica do handoff).
        detail = "already_protected"
    else:  # CLOSED
        # Round 3 A10: reabertura de CLOSED é ato humano; sinal de provedor
        # não reabre sozinho — registra e alerta.
        detail = "closed_requires_human"

    link.last_applied_event_id = ledger.id
    link.last_occurred_at = event.occurred_at  # type: ignore[assignment]
    ledger.status = "applied"  # type: ignore[assignment]
    ledger.applied_at = ts  # type: ignore[assignment]
    ledger.processing_result = {  # type: ignore[assignment]
        "detail": detail,
        "ownership_state": link.ownership_state,
        "automation_state": link.automation_state,
        "identity_conflict": link.identity_conflict,
    }
    if detail == "transitioned":
        ledger.processing_result["alert"] = alert
    return IngestResult(status="applied", ledger=ledger, link=link, detail=detail)


def _register_duplicate(
    session: Session, existing: CrmLeadEvent, incoming_hash: str
) -> IngestResult:
    existing.attempts = (existing.attempts or 1) + 1  # type: ignore[assignment]
    if existing.payload_hash != incoming_hash:  # type: ignore[misc]
        # Mesmo event_id, payload diferente: nunca reprocessa em silêncio.
        result = dict(existing.processing_result or {})  # type: ignore[arg-type, misc]
        result["divergent_payload_hashes"] = sorted(  # type: ignore[arg-type]
            set(result.get("divergent_payload_hashes", []) + [incoming_hash])  # type: ignore[arg-type, misc]
        )
        existing.processing_result = result  # type: ignore[assignment]
        return IngestResult(status="duplicate", ledger=existing, detail="duplicate_divergent")
    return IngestResult(status="duplicate", ledger=existing, detail="duplicate")
