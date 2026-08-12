"""Métricas locais do handoff — Rounds 4 §5, 6 §10 e 7 §10.

Distinção ESTRUTURAL entre zero e não-observável: zero significa "medimos e
não aconteceu"; UNOBSERVABLE significa "não temos instrumento para saber".
Uma métrica não observável não tem valor numérico — pedir o número levanta
``MetricNotObservable``; conversão para int/float quebra; a exibição devolve
"NÃO OBSERVÁVEL". Um painel não consegue renderizar zero por descuido: ou
trata o caso, ou quebra visivelmente.

``rumy_send_after_block`` permanece não-observável até o Rumy fornecer
evidência técnica de envio (P0-15). MANUALLY_CONFIRMED **não** torna a
métrica observável — confirmação procedimental não é telemetria (Round 7 §10).
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.crm_handoff import CrmLeadEvent, CrmLeadLink, CrmStateTransition
from app.services.handoff.capability import (
    RUMY_SEND_OBSERVABILITY_CAPABILITY,
    RUMY_SUPPRESSION_CAPABILITY,
    ProviderCapability,
)
from app.services.handoff.identity import PROTECTED_OWNERSHIP_STATES
from app.services.handoff.ownership import (
    BUSINESS_CALENDAR_VERSION,
    HOLIDAYS_SUPPORTED,
    AutomationState,
    OwnershipState,
    accept_sla_breached,
    business_hours_between,
    first_action_sla_breached,
    pause_confirmation_missing,
    pause_sla_breached,
    uncontained_exposure,
)


class MetricNotObservable(Exception):
    """Levantada ao pedir o valor numérico de uma métrica sem instrumento."""


class UnobservableMetric:
    """Métrica sem instrumento de observação — sem valor numérico possível.

    ``.value`` levanta MetricNotObservable("ausência de evidência não é zero");
    int()/float() quebram; ``display()`` devolve "NÃO OBSERVÁVEL"; comparação
    com 0 é False. O errado é impossível, não apenas desencorajado.
    """

    _MSG = "ausência de evidência não é zero"

    def __init__(self, reason: str = "instrumento indisponível"):
        self.reason = reason

    @property
    def value(self):  # noqa: ANN201 — sempre levanta
        raise MetricNotObservable(self._MSG)

    def display(self) -> str:
        return "NÃO OBSERVÁVEL"

    def __int__(self):
        raise MetricNotObservable(self._MSG)

    def __float__(self):
        raise MetricNotObservable(self._MSG)

    def __index__(self):
        raise MetricNotObservable(self._MSG)

    def __eq__(self, other) -> bool:
        return isinstance(other, UnobservableMetric)

    def __hash__(self) -> int:
        return hash(("UnobservableMetric", self.reason))

    def __repr__(self) -> str:
        return f"UNOBSERVABLE({self.reason})"

    __str__ = __repr__


def rumy_send_after_block() -> UnobservableMetric | int:
    """A métrica crítica do piloto (Rounds 2 §11 / 6 §10 / 7 §10).

    Observável somente quando o Rumy expuser evento/log de envio (P0-15) —
    capacidade hoje UNKNOWN_CAPABILITY. Quando existir instrumento, zero
    passará a significar "medimos e não aconteceu".
    """
    if RUMY_SEND_OBSERVABILITY_CAPABILITY != ProviderCapability.SUPPORTED:
        return UnobservableMetric("RUMY P0-15 sem resposta — sem log de envios")
    raise NotImplementedError("instrumento chega com F5/P0-15")


def _seconds_agg(pairs: list[float]) -> dict[str, Any]:
    if not pairs:
        return {"count": 0, "avg_seconds": None, "max_seconds": None}
    return {
        "count": len(pairs),
        "avg_seconds": round(sum(pairs) / len(pairs), 1),
        "max_seconds": round(max(pairs), 1),
    }


def local_snapshot(session: Session, tenant_id: Optional[uuid.UUID] = None) -> dict[str, Any]:
    """Fotografia das métricas locais (Round 7 §10) — sempre recomputável."""
    ev = session.query(CrmLeadEvent.status, func.count()).group_by(CrmLeadEvent.status)
    lk = session.query(CrmLeadLink)
    tr = session.query(CrmStateTransition).filter(
        CrmStateTransition.axis == "alert", CrmStateTransition.to_state == "uncontained_exposure"
    )
    if tenant_id is not None:
        ev = ev.filter(CrmLeadEvent.tenant_id == tenant_id)
        lk = lk.filter(CrmLeadLink.tenant_id == tenant_id)
        tr = tr.filter(CrmStateTransition.tenant_id == tenant_id)

    events_by_status = {status: count for status, count in ev.all()}
    links = lk.all()

    ownership_counts: dict[str, int] = {}
    automation_counts: dict[str, int] = {}
    pause_secs: list[float] = []
    accept_secs: list[float] = []
    action_secs: list[float] = []
    for link in links:
        ownership_counts[link.ownership_state] = ownership_counts.get(link.ownership_state, 0) + 1
        automation_counts[link.automation_state] = (
            automation_counts.get(link.automation_state, 0) + 1
        )
        if (
            link.handoff_requested_at
            and link.suppression_confirmed_at
            and link.automation_state
            in (
                AutomationState.MANUALLY_CONFIRMED.value,
                AutomationState.SUPPRESSION_CONFIRMED.value,
            )
        ):
            pause_secs.append(
                business_hours_between(
                    link.handoff_requested_at, link.suppression_confirmed_at
                ).total_seconds()
            )
        if link.handoff_requested_at and link.handoff_accepted_at:
            accept_secs.append(
                business_hours_between(
                    link.handoff_requested_at, link.handoff_accepted_at
                ).total_seconds()
            )
        if link.handoff_accepted_at and link.first_human_action_at:
            action_secs.append(
                business_hours_between(
                    link.handoff_accepted_at, link.first_human_action_at
                ).total_seconds()
            )

    handoff_without_owner = sum(
        1
        for link in links
        if link.ownership_state == OwnershipState.HANDOFF_REQUESTED.value
        and link.owner_ref is None
    )
    without_pause_confirmation = sum(1 for link in links if pause_confirmation_missing(link))

    return {
        "events_by_status": events_by_status,
        "handoff_requested": events_by_status.get("applied", 0),
        "duplicate_handoff": events_by_status.get("duplicate", 0),
        "quarantined": events_by_status.get("quarantined", 0),
        "links_by_ownership": ownership_counts,
        "links_by_automation": automation_counts,
        # Round 7 §10 — três relógios, jamais colapsados:
        "handoff_to_manual_pause_seconds": _seconds_agg(pause_secs),
        "handoff_to_human_owner_seconds": _seconds_agg(accept_secs),
        "human_owner_to_first_action_seconds": _seconds_agg(action_secs),
        "manual_pause_sla_breaches": sum(1 for link in links if pause_sla_breached(link)),
        "accept_sla_breaches": sum(1 for link in links if accept_sla_breached(link)),
        "first_action_sla_breaches": sum(
            1 for link in links if first_action_sla_breached(link)
        ),
        "uncontained_exposure_count": max(
            tr.count(), sum(1 for link in links if uncontained_exposure(link))
        ),
        # §13: HUMAN_OWNED sem pausa é situação CRÍTICA, não sucesso
        "handoffs_without_pause_confirmation": without_pause_confirmation,
        "pause_confirmation_missing_critical": without_pause_confirmation > 0,
        "handoffs_without_owner": handoff_without_owner,
        "protected_persons": len(
            {
                link.person_identity_id
                for link in links
                if link.person_identity_id is not None
                and link.ownership_state in PROTECTED_OWNERSHIP_STATES
            }
        ),
        "identity_conflicts": sum(1 for link in links if link.identity_conflict),
        # DEC-7: capacidade do fornecedor — silêncio nunca vira UNSUPPORTED
        "rumy_suppression_capability": RUMY_SUPPRESSION_CAPABILITY.value,
        "rumy_send_after_block": rumy_send_after_block(),
        # Round 7 §3: registro explícito do calendário
        "business_calendar_version": BUSINESS_CALENDAR_VERSION,
        "holidays_supported": HOLIDAYS_SUPPORTED,
    }
