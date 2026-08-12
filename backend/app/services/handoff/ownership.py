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
import json
import logging
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.models.admin_audit import AdminAuditLog
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
    """Eixo de permissão de outbound.

    DEC-8 (Round 7): SUPPRESSION_CONFIRMED = confirmação TÉCNICA observável
    (leitura/ack do provedor — inalcançável no Caminho C, onde não lemos o
    Rumy); MANUALLY_CONFIRMED = confirmação PROCEDIMENTAL humana (operador
    declarou e registrou evidência da pausa no sistema externo). Painéis,
    métricas e auditoria preservam a diferença — confundi-los seria maquiar
    garantia procedimental como técnica.
    """

    ACTIVE = "ACTIVE"
    SUPPRESSION_REQUESTED = "SUPPRESSION_REQUESTED"
    SUPPRESSION_CONFIRMED = "SUPPRESSION_CONFIRMED"
    MANUALLY_CONFIRMED = "MANUALLY_CONFIRMED"


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

    link.ownership_state = to_state.value
    _audit(
        session, link, "ownership", frm.value, to_state.value, actor_type, actor_ref, reason,
        event_id,
    )

    if to_state == OwnershipState.HANDOFF_REQUESTED:
        link.handoff_requested_at = ts
        # DEC-1: supressão começa AQUI, localmente, antes de qualquer remoto.
        if link.automation_state == AutomationState.ACTIVE.value:
            link.automation_state = AutomationState.SUPPRESSION_REQUESTED.value
            link.suppression_requested_at = ts
            _audit(
                session, link, "automation", AutomationState.ACTIVE.value,
                AutomationState.SUPPRESSION_REQUESTED.value, ActorType.SYSTEM, None,
                "DEC-1: supressão local no pedido de handoff", event_id,
            )
        _sync_dec5_suppression(session, link)
    elif to_state == OwnershipState.HUMAN_OWNED:
        link.handoff_accepted_at = ts
        if actor_ref:
            link.owner_ref = actor_ref
        _sync_dec5_suppression(session, link)
    elif to_state == OwnershipState.AUTOMATED:
        # Dupla trava: religar automação exige confirmação de que a supressão
        # foi desfeita no provedor. Sem ela, ownership volta mas outbound
        # permanece bloqueado (automation_state intacto).
        if suppression_lift_confirmed:
            prev = link.automation_state
            link.automation_state = AutomationState.ACTIVE.value
            _audit(
                session, link, "automation", prev, AutomationState.ACTIVE.value, actor_type,
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
    if link.automation_state != AutomationState.SUPPRESSION_REQUESTED.value:
        raise InvalidTransition(
            f"confirmação exige SUPPRESSION_REQUESTED (atual: {link.automation_state})"
        )
    link.automation_state = AutomationState.SUPPRESSION_CONFIRMED.value
    link.suppression_confirmed_at = _now(now)
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
        link.first_human_action_at = _now(now)
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
    if link.identity_conflict:
        return False, "identity_conflict"
    if link.ownership_state != OwnershipState.AUTOMATED.value:
        return False, f"ownership={link.ownership_state}"
    if link.automation_state != AutomationState.ACTIVE.value:
        return False, f"automation={link.automation_state}"
    ids = [link.person_identity_id] if link.person_identity_id else []
    if ids and person_protected(session, link.tenant_id, ids):
        return False, "person_protected"  # DEC-5: outro lead da MESMA pessoa protege este
    return True, "ok"


# ── SLA (Round 4 §12 — dois relógios) ────────────────────────────────────────

_BUSINESS_TZ = ZoneInfo("America/Sao_Paulo")
_BUSINESS_START = time(9, 0)
_BUSINESS_END = time(18, 0)
# Round 7 §3: expediente aprovado provisoriamente (seg–sex 09–18 SP).
# Feriados NÃO tratados por decisão explícita — sem biblioteca de calendário
# escondida; se o piloto exigir, abre-se decisão específica.
BUSINESS_CALENDAR_VERSION = "weekday_only_v1"
HOLIDAYS_SUPPORTED = False


def pause_sla() -> timedelta:
    """DEC-6 (Round 7): pausa manual no Rumy ≤ 5 min úteis — relógio próprio.

    É o relógio de CONTENÇÃO: mede a janela de exposição do Caminho C. Mais
    apertado que o de assunção por definição — esse número é a exposição que
    Produto aceita.
    """
    return timedelta(minutes=settings.HANDOFF_PAUSE_SLA_MINUTES)


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
    return business_hours_between(link.handoff_requested_at, end)


def time_to_human_action(link: CrmLeadLink, now: Optional[datetime] = None) -> Optional[timedelta]:
    if link.handoff_accepted_at is None:
        return None
    end = link.first_human_action_at or _now(now)
    return business_hours_between(link.handoff_accepted_at, end)


_PAUSE_DONE_STATES = frozenset(
    {AutomationState.SUPPRESSION_CONFIRMED.value, AutomationState.MANUALLY_CONFIRMED.value}
)


def pause_pending(link: CrmLeadLink) -> bool:
    """Pausa remota ainda não registrada (trava local aplicada, Rumy presumido falando)."""
    return (
        link.handoff_requested_at is not None
        and link.automation_state == AutomationState.SUPPRESSION_REQUESTED.value
    )


def time_to_manual_pause(link: CrmLeadLink, now: Optional[datetime] = None) -> Optional[timedelta]:
    if link.handoff_requested_at is None:
        return None
    end = (
        link.suppression_confirmed_at
        if link.automation_state in _PAUSE_DONE_STATES and link.suppression_confirmed_at
        else _now(now)
    )
    return business_hours_between(link.handoff_requested_at, end)


def pause_sla_breached(link: CrmLeadLink, now: Optional[datetime] = None) -> bool:
    """Relógio de contenção estourado — independe do ownership: HUMAN_OWNED
    NÃO mascara ausência de pausa (Round 7 §13)."""
    if not pause_pending(link):
        return False
    elapsed = time_to_manual_pause(link, now=now)
    return elapsed is not None and elapsed > pause_sla()


def uncontained_exposure(link: CrmLeadLink, now: Optional[datetime] = None) -> bool:
    """2× o SLA de pausa sem confirmação: exposição não contida — incidente."""
    if not pause_pending(link):
        return False
    elapsed = time_to_manual_pause(link, now=now)
    return elapsed is not None and elapsed > 2 * pause_sla()


def pause_confirmation_missing(link: CrmLeadLink) -> bool:
    """Situação crítica do §13: lead sob atenção (ou já assumido) sem pausa
    registrada — HUMAN_OWNED + SUPPRESSION_REQUESTED é alarme, não sucesso."""
    return (
        link.ownership_state
        in (OwnershipState.HANDOFF_REQUESTED.value, OwnershipState.HUMAN_OWNED.value)
        and link.automation_state == AutomationState.SUPPRESSION_REQUESTED.value
    )


def _admin_audit(session: Session, actor: str, action: str, link: CrmLeadLink, detail: dict) -> None:
    session.add(
        AdminAuditLog(
            actor_email=actor,
            action=action,
            target_type="crm_lead_link",
            target_id=str(link.id),
            detail=detail,
        )
    )


def register_manual_pause(
    session: Session,
    link: CrmLeadLink,
    actor_ref: str,
    evidence: str,
    now: Optional[datetime] = None,
) -> CrmLeadLink:
    """Registra a pausa MANUAL feita pelo operador no Rumy (Caminho C, DEC-8).

    Exige ator identificado e evidência não-vazia (descrição da ação + instante
    — Round 7 §8; screenshot é complementar, não obrigatório). Sem ator ou sem
    evidência, a pausa NÃO é registrável. Resultado: MANUALLY_CONFIRMED —
    afirmação de pessoa, grau probatório menor que SUPPRESSION_CONFIRMED, e o
    dado carrega a diferença.
    """
    if not actor_ref or not actor_ref.strip():
        raise InvalidTransition("pausa manual exige ator identificado (§8)")
    if not evidence or not evidence.strip():
        raise InvalidTransition("pausa manual exige evidência não-vazia (§8)")
    if link.automation_state != AutomationState.SUPPRESSION_REQUESTED.value:
        raise InvalidTransition(
            f"pausa manual exige SUPPRESSION_REQUESTED (atual: {link.automation_state})"
        )
    ts = _now(now)
    link.automation_state = AutomationState.MANUALLY_CONFIRMED.value
    link.suppression_confirmed_at = ts
    payload = {"action": evidence.strip(), "origem": "rumy", "registered_at": ts.isoformat()}
    _audit(
        session, link, "automation", AutomationState.SUPPRESSION_REQUESTED.value,
        AutomationState.MANUALLY_CONFIRMED.value, ActorType.HUMAN, actor_ref,
        json.dumps(payload, ensure_ascii=False), None,
    )
    _admin_audit(session, actor_ref, "handoff.manual_pause", link, payload)
    session.flush()
    return link


def register_manual_reactivation(
    session: Session,
    link: CrmLeadLink,
    actor_ref: str,
    evidence: str,
    now: Optional[datetime] = None,
) -> CrmLeadLink:
    """Reativação manual (Round 7 §9): RELEASED → AUTOMATED, sempre por humano.

    No Caminho C a retomada também é manual: exige evidência de que o Rumy foi
    reativado — sem ela, o contato não pode ser representado como seguramente
    automatizado. Nunca automática (a matriz já proíbe; aqui exige-se também a
    evidência).
    """
    if not actor_ref or not actor_ref.strip():
        raise InvalidTransition("reativação exige ator identificado (§9)")
    if not evidence or not evidence.strip():
        raise InvalidTransition("reativação exige evidência de retomada no Rumy (§9)")
    if link.ownership_state != OwnershipState.RELEASED.value:
        raise InvalidTransition(
            f"reativação exige RELEASED (atual: {link.ownership_state})"
        )
    ts = _now(now)
    transition_ownership(
        session, link, OwnershipState.AUTOMATED, ActorType.HUMAN, actor_ref=actor_ref,
        reason=evidence.strip(), now=ts, suppression_lift_confirmed=True,
    )
    _admin_audit(
        session, actor_ref, "handoff.manual_reactivation", link,
        {"evidence": evidence.strip(), "at": ts.isoformat()},
    )
    session.flush()
    return link


def accept_sla_breached(link: CrmLeadLink, now: Optional[datetime] = None) -> bool:
    """True se o pedido de handoff estourou o SLA de aceite sem HUMAN_OWNED.

    Estouro ESCALA para humano — jamais devolve o lead à automação (matriz).
    """
    if link.ownership_state != OwnershipState.HANDOFF_REQUESTED.value:
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
