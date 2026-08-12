"""Máquinas de ownership/automation, guards e SLA — F3 do Round 4.

Dois eixos independentes do estágio comercial (Round 3 §7, Round 4 §7):

- ownership_state: AUTOMATED → HANDOFF_REQUESTED → HUMAN_OWNED → RELEASED →
  (re-arme explícito) AUTOMATED; CLOSED encerra. A supressão começa em
  HANDOFF_REQUESTED (DEC-1) — o SLA humano não autoriza a automação a falar.
- automation_state: ACTIVE → SUPPRESSION_REQUESTED → SUPPRESSION_CONFIRMED.
  Round 4 §15: distinção formal entre pedido e confirmação de supressão.

Dupla trava (Round 4 §11): RELEASED ≠ AUTOMATED. Liberar o controle humano não
religa outbound; religar exige transição explícita RELEASED→AUTOMATED por ator
humano E confirmação de que a supressão foi desfeita no provedor
(suppression_lift_confirmed) — sem a confirmação, o outbound segue bloqueado.

Toda transição é auditada em crm_state_transitions com ator (bot × humano
nunca se confundem). Nenhuma função aqui consulta feature flag: proteção
persiste com flags OFF (desligar flag nunca re-permite outbound).
"""

from __future__ import annotations

import enum
import logging
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.models.crm_handoff import CrmLeadLink, CrmStateTransition
from app.models.prospect_suppression import ProspectSuppression
from app.services.handoff.identity import person_protected

logger = logging.getLogger(__name__)

_DEC5_REASON_PREFIX = "DEC-5 handoff protection"


class OwnershipState(str, enum.Enum):
    AUTOMATED = "AUTOMATED"
    HANDOFF_REQUESTED = "HANDOFF_REQUESTED"
    HUMAN_OWNED = "HUMAN_OWNED"
    RELEASED = "RELEASED"
    CLOSED = "CLOSED"


class AutomationState(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUPPRESSION_REQUESTED = "SUPPRESSION_REQUESTED"
    SUPPRESSION_CONFIRMED = "SUPPRESSION_CONFIRMED"


class ActorType(str, enum.Enum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
    PROVIDER_EVENT = "PROVIDER_EVENT"


class InvalidTransition(Exception):
    """Transição fora da matriz (ou ator não autorizado para ela)."""


_H = frozenset({ActorType.HUMAN})
_ANY = frozenset({ActorType.HUMAN, ActorType.SYSTEM, ActorType.PROVIDER_EVENT})

# Matriz oficial (Round 3 A10 revista no Round 4 §7). Ausência = proibido.
# Proibições estruturais: HANDOFF_REQUESTED→AUTOMATED (timeout ESCALA, nunca
# devolve ao bot) e HUMAN_OWNED→AUTOMATED direto (só via RELEASED).
_ALLOWED: dict[tuple[OwnershipState, OwnershipState], frozenset[ActorType]] = {
    (OwnershipState.AUTOMATED, OwnershipState.HANDOFF_REQUESTED): _ANY,
    (OwnershipState.AUTOMATED, OwnershipState.HUMAN_OWNED): _H,  # assume espontâneo
    (OwnershipState.AUTOMATED, OwnershipState.CLOSED): _H,
    (OwnershipState.HANDOFF_REQUESTED, OwnershipState.HUMAN_OWNED): _H,
    (OwnershipState.HANDOFF_REQUESTED, OwnershipState.CLOSED): _H,
    (OwnershipState.HUMAN_OWNED, OwnershipState.HANDOFF_REQUESTED): _H,  # re-pedido
    (OwnershipState.HUMAN_OWNED, OwnershipState.RELEASED): _H,
    (OwnershipState.HUMAN_OWNED, OwnershipState.CLOSED): _H,
    (OwnershipState.RELEASED, OwnershipState.AUTOMATED): _H,  # re-arme explícito
    (OwnershipState.RELEASED, OwnershipState.HANDOFF_REQUESTED): _ANY,  # novo sinal
    (OwnershipState.RELEASED, OwnershipState.HUMAN_OWNED): _H,
    (OwnershipState.RELEASED, OwnershipState.CLOSED): _H,
    (OwnershipState.CLOSED, OwnershipState.HANDOFF_REQUESTED): _H,  # reabertura humana
}


def _now(now: Optional[datetime]) -> datetime:
    return now or datetime.now(timezone.utc)


def _audit(
    session: Session,
    link: CrmLeadLink,
    axis: str,
    from_state: Optional[str],
    to_state: str,
    actor_type: ActorType,
    actor_ref: Optional[str],
    reason: Optional[str],
    event_id: Optional[uuid.UUID],
) -> None:
    session.add(
        CrmStateTransition(
            tenant_id=link.tenant_id,
            lead_link_id=link.id,
            axis=axis,
            from_state=from_state,
            to_state=to_state,
            actor_type=actor_type.value,
            actor_ref=actor_ref,
            reason=reason,
            event_id=event_id,
        )
    )


def _sync_dec5_suppression(session: Session, link: CrmLeadLink) -> None:
    """Espelha a proteção DEC-5 na lista de supressão da prospecção em lote.

    ProspectSuppression já é filtro DURO e incondicional na geração de listas
    (PO-2026-07-SALES-001) — inserir a pessoa ali estende a proteção ao pipeline
    de lote existente sem nenhum efeito externo (é banco local). Limitação
    documentada: a tabela casa por e-mail/CNPJ; identidade só-LinkedIn não é
    espelhável ali (fica coberta pelo guard outbound_allowed).
    """
    if link.person_identity_id is None:
        return
    from app.models.crm_handoff import CrmPersonIdentity  # import local: evita ciclo

    identity = session.get(CrmPersonIdentity, link.person_identity_id)
    if identity is None or identity.email_normalized is None:
        return
    reason = f"{_DEC5_REASON_PREFIX} (person={identity.id})"
    exists = (
        session.query(ProspectSuppression)
        .filter(
            ProspectSuppression.email == identity.email_normalized,
            ProspectSuppression.status == "lead_ativo",
            ProspectSuppression.reason == reason,
        )
        .one_or_none()
    )
    if exists is None:
        session.add(
            ProspectSuppression(
                email=identity.email_normalized, status="lead_ativo", reason=reason
            )
        )


def _lift_dec5_suppression(session: Session, link: CrmLeadLink) -> None:
    """Remove APENAS as linhas de supressão criadas pela DEC-5 para esta pessoa."""
    if link.person_identity_id is None:
        return
    from app.models.crm_handoff import CrmPersonIdentity

    identity = session.get(CrmPersonIdentity, link.person_identity_id)
    if identity is None or identity.email_normalized is None:
        return
    reason = f"{_DEC5_REASON_PREFIX} (person={identity.id})"
    session.query(ProspectSuppression).filter(
        ProspectSuppression.email == identity.email_normalized,
        ProspectSuppression.status == "lead_ativo",
        ProspectSuppression.reason == reason,
    ).delete(synchronize_session=False)


def transition_ownership(
    session: Session,
    link: CrmLeadLink,
    to_state: OwnershipState,
    actor_type: ActorType,
    actor_ref: Optional[str] = None,
    reason: Optional[str] = None,
    event_id: Optional[uuid.UUID] = None,
    now: Optional[datetime] = None,
    suppression_lift_confirmed: bool = False,
) -> CrmLeadLink:
    """Aplica uma transição de ownership com guards, timestamps e auditoria."""
    ts = _now(now)
    frm = OwnershipState(link.ownership_state)
    if frm == to_state:
        raise InvalidTransition(f"transição nula {frm.value}→{to_state.value}")
    allowed_actors = _ALLOWED.get((frm, to_state))
    if allowed_actors is None:
        raise InvalidTransition(f"transição proibida {frm.value}→{to_state.value}")
    if actor_type not in allowed_actors:
        raise InvalidTransition(
            f"ator {actor_type.value} não autorizado para {frm.value}→{to_state.value}"
        )
    if to_state in (OwnershipState.RELEASED, OwnershipState.AUTOMATED) and not reason:
        raise InvalidTransition(
            f"transição para {to_state.value} exige reason auditável (Round 4 §11)"
        )

    link.ownership_state = to_state.value  # type: ignore[assignment]
    _audit(
        session, link, "ownership", frm.value, to_state.value, actor_type, actor_ref, reason,
        event_id,
    )

    if to_state == OwnershipState.HANDOFF_REQUESTED:
        link.handoff_requested_at = ts  # type: ignore[assignment]
        # DEC-1: supressão começa AQUI, localmente, antes de qualquer remoto.
        if link.automation_state == AutomationState.ACTIVE.value:  # type: ignore[misc]
            link.automation_state = AutomationState.SUPPRESSION_REQUESTED.value  # type: ignore[assignment]
            link.suppression_requested_at = ts  # type: ignore[assignment]
            _audit(
                session, link, "automation", AutomationState.ACTIVE.value,
                AutomationState.SUPPRESSION_REQUESTED.value, ActorType.SYSTEM, None,
                "DEC-1: supressão local no pedido de handoff", event_id,
            )
        _sync_dec5_suppression(session, link)
    elif to_state == OwnershipState.HUMAN_OWNED:
        link.handoff_accepted_at = ts  # type: ignore[assignment]
        if actor_ref:
            link.owner_ref = actor_ref  # type: ignore[assignment]
        _sync_dec5_suppression(session, link)
    elif to_state == OwnershipState.AUTOMATED:
        # Dupla trava: religar automação exige confirmação de que a supressão
        # foi desfeita no provedor. Sem ela, ownership volta mas outbound
        # permanece bloqueado (automation_state intacto).
        if suppression_lift_confirmed:
            prev = link.automation_state
            link.automation_state = AutomationState.ACTIVE.value  # type: ignore[assignment]
            _audit(
                session, link, "automation", prev, AutomationState.ACTIVE.value, actor_type,  # type: ignore[arg-type]
                actor_ref, "re-arme explícito com supressão desfeita comprovada", event_id,
            )
            _lift_dec5_suppression(session, link)
        else:
            logger.info(
                "handoff_rearm_without_lift link=%s: ownership=AUTOMATED mas outbound segue "
                "bloqueado (automation_state=%s)",
                link.id,
                link.automation_state,
            )

    session.flush()
    return link


def confirm_suppression(
    session: Session,
    link: CrmLeadLink,
    actor_type: ActorType = ActorType.SYSTEM,
    actor_ref: Optional[str] = None,
    now: Optional[datetime] = None,
) -> CrmLeadLink:
    """SUPPRESSION_REQUESTED → SUPPRESSION_CONFIRMED (Round 4 §15).

    Nesta fatia só é alcançável por teste/uso interno — o comando real ao Rumy
    (F5) não está autorizado; quando existir, a confirmação vem da resposta/
    consulta do provedor.
    """
    if link.automation_state != AutomationState.SUPPRESSION_REQUESTED.value:  # type: ignore[misc]
        raise InvalidTransition(
            f"confirmação exige SUPPRESSION_REQUESTED (atual: {link.automation_state})"
        )
    link.automation_state = AutomationState.SUPPRESSION_CONFIRMED.value  # type: ignore[assignment]
    link.suppression_confirmed_at = _now(now)  # type: ignore[assignment]
    _audit(
        session, link, "automation", AutomationState.SUPPRESSION_REQUESTED.value,
        AutomationState.SUPPRESSION_CONFIRMED.value, actor_type, actor_ref, None, None,
    )
    session.flush()
    return link


#: atividades que CONTAM como primeira ação humana (Round 4 §12)
SUBSTANTIVE_ACTION_KINDS: frozenset[str] = frozenset(
    {"message", "call", "meeting", "substantive_activity"}
)
#: atividades que NÃO contam (abrir/visualizar/assumir/trocar owner/nota administrativa)
NON_COUNTING_ACTION_KINDS: frozenset[str] = frozenset(
    {"open", "view", "assume", "owner_change", "admin_note"}
)


def register_human_action(
    session: Session,
    link: CrmLeadLink,
    kind: str,
    actor_ref: str,
    now: Optional[datetime] = None,
) -> bool:
    """Registra ação humana; retorna True se contou como PRIMEIRA ação substantiva.

    handoff_accepted ≠ human_first_action: 'assume' e afins nunca param o
    relógio de time_to_human_action.
    """
    if kind not in SUBSTANTIVE_ACTION_KINDS:
        if kind not in NON_COUNTING_ACTION_KINDS:
            raise ValueError(f"kind desconhecido: {kind!r}")
        return False
    counted = False
    if link.first_human_action_at is None:
        link.first_human_action_at = _now(now)  # type: ignore[assignment]
        counted = True
    _audit(
        session, link, "activity", None, f"human_action:{kind}", ActorType.HUMAN, actor_ref,
        None, None,
    )
    session.flush()
    return counted


def outbound_allowed(session: Session, link: CrmLeadLink) -> tuple[bool, str]:
    """Permissão CONJUNTIVA de outbound automatizado (Round 3 A11, Round 4 §15).

    Qualquer incerteza ⇒ bloqueado. Flags não entram aqui de propósito: elas só
    podem bloquear a montante (nunca re-permitir), e a proteção de pessoa
    (DEC-5) vale mesmo com o sistema inteiro desligado.
    """
    if link.identity_conflict:  # type: ignore[misc]
        return False, "identity_conflict"
    if link.ownership_state != OwnershipState.AUTOMATED.value:  # type: ignore[misc]
        return False, f"ownership={link.ownership_state}"
    if link.automation_state != AutomationState.ACTIVE.value:  # type: ignore[misc]
        return False, f"automation={link.automation_state}"
    ids = [link.person_identity_id] if link.person_identity_id else []  # type: ignore[misc]
    if ids and person_protected(session, link.tenant_id, ids):  # type: ignore[arg-type]
        return False, "person_protected"  # DEC-5: outro lead da MESMA pessoa protege este
    return True, "ok"


# ── SLA (Round 4 §12 — dois relógios) ────────────────────────────────────────

_BUSINESS_TZ = ZoneInfo("America/Sao_Paulo")
_BUSINESS_START = time(9, 0)
_BUSINESS_END = time(18, 0)


def accept_sla() -> timedelta:
    """SLA provisório de aceite (Round 6 §8): 15 min úteis, configurável."""
    return timedelta(minutes=settings.HANDOFF_ACCEPT_SLA_MINUTES)


def first_action_sla() -> timedelta:
    """SLA provisório da 1ª ação substantiva (Round 6 §8): 30 min úteis."""
    return timedelta(minutes=settings.HANDOFF_FIRST_ACTION_SLA_MINUTES)


def business_hours_between(start: datetime, end: datetime) -> timedelta:
    """Tempo útil (seg–sex, 09:00–18:00 America/Sao_Paulo) entre dois instantes.

    Feriados ficam fora do escopo do piloto (documentado; calendário entra em
    fatia futura se Produto exigir).
    """
    if end <= start:
        return timedelta(0)
    start_l = start.astimezone(_BUSINESS_TZ)
    end_l = end.astimezone(_BUSINESS_TZ)
    total = timedelta(0)
    cursor = start_l.date()
    while cursor <= end_l.date():
        if cursor.weekday() < 5:  # seg–sex
            day_open = datetime.combine(cursor, _BUSINESS_START, tzinfo=_BUSINESS_TZ)
            day_close = datetime.combine(cursor, _BUSINESS_END, tzinfo=_BUSINESS_TZ)
            lo = max(start_l, day_open)
            hi = min(end_l, day_close)
            if hi > lo:
                total += hi - lo
        cursor += timedelta(days=1)
    return total


def time_to_accept(link: CrmLeadLink, now: Optional[datetime] = None) -> Optional[timedelta]:
    if link.handoff_requested_at is None:
        return None
    end = link.handoff_accepted_at or _now(now)
    return business_hours_between(link.handoff_requested_at, end)  # type: ignore[arg-type]


def time_to_human_action(link: CrmLeadLink, now: Optional[datetime] = None) -> Optional[timedelta]:
    if link.handoff_accepted_at is None:
        return None
    end = link.first_human_action_at or _now(now)
    return business_hours_between(link.handoff_accepted_at, end)  # type: ignore[arg-type]


def accept_sla_breached(link: CrmLeadLink, now: Optional[datetime] = None) -> bool:
    """True se o pedido de handoff estourou o SLA de aceite sem HUMAN_OWNED.

    Estouro ESCALA para humano — jamais devolve o lead à automação (matriz).
    """
    if link.ownership_state != OwnershipState.HANDOFF_REQUESTED.value:  # type: ignore[misc]
        return False
    elapsed = time_to_accept(link, now=now)
    return elapsed is not None and elapsed > accept_sla()


def first_action_sla_breached(link: CrmLeadLink, now: Optional[datetime] = None) -> bool:
    """True se HUMAN_OWNED sem 1ª ação substantiva dentro do SLA (relógio 2).

    Independente do relógio de aceite: assumir rápido não satisfaz este SLA
    (Round 6 §8 — "'assumir' não satisfaz o segundo").
    """
    if link.ownership_state != OwnershipState.HUMAN_OWNED.value:
        return False
    if link.first_human_action_at is not None:
        return False
    elapsed = time_to_human_action(link, now=now)
    return elapsed is not None and elapsed > first_action_sla()
