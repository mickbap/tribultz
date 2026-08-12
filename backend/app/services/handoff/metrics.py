"""Métricas locais do handoff — F3 do Round 4 (derivadas do banco, sem push).

Estas funções materializam as propriedades observáveis do Round 2 §11 que já
são mensuráveis SEM o Rumy (rumy_send_after_block exige o log de envios do
provedor — RUMY-O15..O19 — e por ordem do Round 4 §5 NÃO é declarada zero sem
instrumento: ausência de evidência não equivale a zero).
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.crm_handoff import CrmLeadEvent, CrmLeadLink
from app.services.handoff.identity import PROTECTED_OWNERSHIP_STATES
from app.services.handoff.ownership import OwnershipState, accept_sla_breached


def local_snapshot(session: Session, tenant_id: Optional[uuid.UUID] = None) -> dict[str, Any]:
    """Fotografia das métricas locais (contadores derivados, sempre recomputáveis)."""
    ev = session.query(CrmLeadEvent.status, func.count()).group_by(CrmLeadEvent.status)
    lk = session.query(CrmLeadLink)
    if tenant_id is not None:
        ev = ev.filter(CrmLeadEvent.tenant_id == tenant_id)
        lk = lk.filter(CrmLeadLink.tenant_id == tenant_id)

    events_by_status = {status: count for status, count in ev.all()}
    links = lk.all()

    ownership_counts: dict[str, int] = {}
    for link in links:
        ownership_counts[link.ownership_state] = ownership_counts.get(link.ownership_state, 0) + 1  # type: ignore[arg-type, misc]

    handoff_without_owner = sum(
        1
        for link in links
        if link.ownership_state == OwnershipState.HANDOFF_REQUESTED.value  # type: ignore[misc]
        and link.owner_ref is None
    )
    sla_breaches = sum(1 for link in links if accept_sla_breached(link))
    protected_persons = len(
        {
            link.person_identity_id
            for link in links
            if link.person_identity_id is not None
            and link.ownership_state in PROTECTED_OWNERSHIP_STATES
        }
    )
    identity_conflicts = sum(1 for link in links if link.identity_conflict)  # type: ignore[misc]

    return {
        "events_by_status": events_by_status,
        "handoff_requested": events_by_status.get("applied", 0),
        "duplicate_handoff": events_by_status.get("duplicate", 0),
        "quarantined": events_by_status.get("quarantined", 0),
        "links_by_ownership": ownership_counts,
        "handoff_without_owner": handoff_without_owner,
        "accept_sla_breaches": sla_breaches,
        "protected_persons": protected_persons,
        "identity_conflicts": identity_conflicts,
        # Round 4 §5: sem instrumento (log de envios do Rumy) esta métrica é
        # explicitamente NÃO-OBSERVÁVEL — nunca reportar zero por ausência.
        "rumy_send_after_block": "UNOBSERVABLE (RUMY-O15..O19 pendentes)",
    }
