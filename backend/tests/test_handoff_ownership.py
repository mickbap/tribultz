"""Round 4 F3: matriz de ownership, dupla trava RELEASED≠AUTOMATED, SLA, ações.

Campanha QA §11: verificar que liberar controle humano NÃO religa outbound,
que timeout de SLA nunca devolve ao bot, e que a supressão DEC-5 espelha na
lista dura da prospecção. DB real com rollback por teste; dados sintéticos.
"""

import os
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.auth import Tenant
from app.models.crm_handoff import CrmLeadLink, CrmStateTransition
from app.models.prospect_suppression import ProspectSuppression
from app.services.handoff.identity import resolve_person
from app.services.handoff.ownership import (
    ActorType,
    AutomationState,
    InvalidTransition,
    OwnershipState,
    accept_sla_breached,
    business_hours_between,
    confirm_suppression,
    outbound_allowed,
    register_human_action,
    transition_ownership,
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SP = ZoneInfo("America/Sao_Paulo")


@pytest.fixture(name="session")
def session_fixture():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(name="tenant_id")
def tenant_fixture(session):
    tenant = Tenant(name=f"Tenant QA {uuid.uuid4().hex[:6]}", slug=f"tenant-qa-{uuid.uuid4()}")
    session.add(tenant)
    session.flush()
    return tenant.id


def _link(session, tenant_id, *, email=None, external_id=None) -> CrmLeadLink:
    person_id = None
    if email:
        person_id = resolve_person(session, tenant_id, email, None).identity.id
    link = CrmLeadLink(
        tenant_id=tenant_id,
        source_system="rumy",
        external_lead_id=external_id or f"lead-sintetico-{uuid.uuid4().hex[:8]}",
        person_identity_id=person_id,
    )
    session.add(link)
    session.flush()
    return link


def _audit_rows(session, link, axis=None):
    q = session.query(CrmStateTransition).filter(CrmStateTransition.lead_link_id == link.id)
    if axis:
        q = q.filter(CrmStateTransition.axis == axis)
    return q.all()


def test_handoff_requested_trava_local_e_espelha_dec5(session, tenant_id):
    link = _link(session, tenant_id, email="pessoa.sintetica@example.test")
    transition_ownership(session, link, OwnershipState.HANDOFF_REQUESTED, ActorType.PROVIDER_EVENT)

    assert link.ownership_state == "HANDOFF_REQUESTED"
    assert link.automation_state == "SUPPRESSION_REQUESTED"  # DEC-1: trava imediata
    assert link.handoff_requested_at is not None
    assert link.suppression_requested_at is not None
    assert outbound_allowed(session, link) == (False, "ownership=HANDOFF_REQUESTED")

    # espelho na lista dura da prospecção em lote (defesa em profundidade)
    row = (
        session.query(ProspectSuppression)
        .filter(ProspectSuppression.email == "pessoa.sintetica@example.test")
        .one()
    )
    assert row.status == "lead_ativo"
    assert "DEC-5" in row.reason

    assert len(_audit_rows(session, link, "ownership")) == 1
    assert len(_audit_rows(session, link, "automation")) == 1


@pytest.mark.parametrize(
    ("start", "target", "actor"),
    [
        ("HANDOFF_REQUESTED", OwnershipState.AUTOMATED, ActorType.HUMAN),  # timeout ESCALA
        ("HANDOFF_REQUESTED", OwnershipState.AUTOMATED, ActorType.SYSTEM),
        ("HUMAN_OWNED", OwnershipState.AUTOMATED, ActorType.HUMAN),  # só via RELEASED
        ("CLOSED", OwnershipState.AUTOMATED, ActorType.HUMAN),
        ("CLOSED", OwnershipState.HUMAN_OWNED, ActorType.HUMAN),
        ("AUTOMATED", OwnershipState.RELEASED, ActorType.HUMAN),
    ],
)
def test_transicoes_proibidas(session, tenant_id, start, target, actor):
    link = _link(session, tenant_id)
    link.ownership_state = start
    with pytest.raises(InvalidTransition):
        transition_ownership(session, link, target, actor, reason="tentativa proibida")


def test_provider_event_nao_pode_aceitar_handoff(session, tenant_id):
    """Aceite é ato humano: bot jamais 'assume' — invariante E-3/E-5."""
    link = _link(session, tenant_id)
    transition_ownership(session, link, OwnershipState.HANDOFF_REQUESTED, ActorType.PROVIDER_EVENT)
    with pytest.raises(InvalidTransition):
        transition_ownership(session, link, OwnershipState.HUMAN_OWNED, ActorType.PROVIDER_EVENT)


def test_aceite_humano_estampa_owner_e_aceite(session, tenant_id):
    link = _link(session, tenant_id)
    transition_ownership(session, link, OwnershipState.HANDOFF_REQUESTED, ActorType.PROVIDER_EVENT)
    transition_ownership(
        session, link, OwnershipState.HUMAN_OWNED, ActorType.HUMAN, actor_ref="ana.qa@6tech.test"
    )
    assert link.handoff_accepted_at is not None
    assert link.owner_ref == "ana.qa@6tech.test"


def test_released_sem_lift_nao_religa_outbound(session, tenant_id):
    """Round 4 §11: RELEASED ≠ AUTOMATED — dupla trava."""
    link = _link(session, tenant_id, email="dupla.trava@example.test")
    transition_ownership(session, link, OwnershipState.HANDOFF_REQUESTED, ActorType.PROVIDER_EVENT)
    transition_ownership(session, link, OwnershipState.HUMAN_OWNED, ActorType.HUMAN, actor_ref="ana")

    # liberar exige reason auditável
    with pytest.raises(InvalidTransition):
        transition_ownership(session, link, OwnershipState.RELEASED, ActorType.HUMAN)
    transition_ownership(
        session, link, OwnershipState.RELEASED, ActorType.HUMAN, reason="lead devolvido [QA]"
    )
    assert outbound_allowed(session, link)[0] is False  # liberar não religa

    # re-arme SEM confirmação de supressão desfeita: ownership volta, outbound NÃO
    transition_ownership(
        session, link, OwnershipState.AUTOMATED, ActorType.HUMAN,
        reason="re-arme sem lift [QA]", suppression_lift_confirmed=False,
    )
    assert link.ownership_state == "AUTOMATED"
    assert link.automation_state == "SUPPRESSION_REQUESTED"
    allowed, why = outbound_allowed(session, link)
    assert allowed is False and why == "automation=SUPPRESSION_REQUESTED"
    # a linha DEC-5 na lista de supressão da prospecção permanece
    assert (
        session.query(ProspectSuppression)
        .filter(ProspectSuppression.email == "dupla.trava@example.test")
        .count()
        == 1
    )


def test_rearm_com_lift_confirmado_religa_e_limpa_dec5(session, tenant_id):
    link = _link(session, tenant_id, email="rearme.completo@example.test")
    transition_ownership(session, link, OwnershipState.HANDOFF_REQUESTED, ActorType.PROVIDER_EVENT)
    confirm_suppression(session, link)
    assert link.automation_state == AutomationState.SUPPRESSION_CONFIRMED.value
    transition_ownership(session, link, OwnershipState.HUMAN_OWNED, ActorType.HUMAN, actor_ref="ana")
    transition_ownership(
        session, link, OwnershipState.RELEASED, ActorType.HUMAN, reason="devolvido [QA]"
    )
    transition_ownership(
        session, link, OwnershipState.AUTOMATED, ActorType.HUMAN,
        reason="re-arme autorizado [QA]", suppression_lift_confirmed=True,
    )
    assert link.automation_state == "ACTIVE"
    assert outbound_allowed(session, link) == (True, "ok")
    assert (
        session.query(ProspectSuppression)
        .filter(ProspectSuppression.email == "rearme.completo@example.test")
        .count()
        == 0
    )


def test_dec5_novo_lead_da_mesma_pessoa_herda_protecao(session, tenant_id):
    """O núcleo da DEC-5: novo external_lead_id ≠ nova permissão de abordagem."""
    protegido = _link(session, tenant_id, email="pessoa.protegida@example.test")
    transition_ownership(
        session, protegido, OwnershipState.HANDOFF_REQUESTED, ActorType.PROVIDER_EVENT
    )

    novo_lead = _link(
        session, tenant_id, email="pessoa.protegida@example.test", external_id="lead-novo-999"
    )
    assert novo_lead.ownership_state == "AUTOMATED"  # o lead em si está livre…
    allowed, why = outbound_allowed(session, novo_lead)
    assert allowed is False and why == "person_protected"  # …mas a PESSOA não


def test_conflito_de_identidade_bloqueia_outbound(session, tenant_id):
    link = _link(session, tenant_id)
    link.identity_conflict = True
    assert outbound_allowed(session, link) == (False, "identity_conflict")


def test_primeira_acao_humana_ignora_administrativo(session, tenant_id):
    link = _link(session, tenant_id)
    assert register_human_action(session, link, "assume", "ana") is False
    assert register_human_action(session, link, "open", "ana") is False
    assert link.first_human_action_at is None
    assert register_human_action(session, link, "message", "ana") is True
    first = link.first_human_action_at
    assert first is not None
    assert register_human_action(session, link, "call", "ana") is False  # já contou
    assert link.first_human_action_at == first
    with pytest.raises(ValueError):
        register_human_action(session, link, "telepatia", "ana")


def test_horas_uteis_atravessando_fim_de_semana():
    sexta_17 = datetime(2026, 8, 14, 17, 0, tzinfo=SP)  # sexta
    segunda_10 = datetime(2026, 8, 17, 10, 0, tzinfo=SP)  # segunda
    assert business_hours_between(sexta_17, segunda_10) == timedelta(hours=2)


def test_sla_de_aceite_estoura_e_escala_nunca_devolve(session, tenant_id):
    link = _link(session, tenant_id)
    quarta_9 = datetime(2026, 8, 12, 9, 0, tzinfo=SP)
    transition_ownership(
        session, link, OwnershipState.HANDOFF_REQUESTED, ActorType.PROVIDER_EVENT, now=quarta_9
    )
    quarta_15 = datetime(2026, 8, 12, 15, 0, tzinfo=SP)  # 6h úteis depois
    assert accept_sla_breached(link, now=quarta_15) is True
    # estourado, a única saída continua sendo humana — devolver ao bot é proibido
    with pytest.raises(InvalidTransition):
        transition_ownership(
            session, link, OwnershipState.AUTOMATED, ActorType.SYSTEM, reason="timeout"
        )
