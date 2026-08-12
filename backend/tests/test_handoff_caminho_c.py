"""Round 7 §13 — campanha QA do Caminho C: pausa manual, três relógios, alerta.

Ataques obrigatórios da ordem, incluindo o crítico: HUMAN_OWNED não pode
mascarar ausência de pausa. Dados 100% sintéticos; nada religa outbound.
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.admin_audit import AdminAuditLog
from app.models.auth import Tenant
from app.models.crm_handoff import CrmLeadLink, CrmStateTransition
from app.services.handoff.alerts import escalate_overdue, raise_pause_alert
from app.services.handoff.capability import (
    RUMY_SUPPRESSION_CAPABILITY,
    ProviderCapability,
    declare_capability,
)
from app.services.handoff.inbox import persist_raw_event, process_raw_event
from app.services.handoff.metrics import (
    MetricNotObservable,
    UnobservableMetric,
    local_snapshot,
    rumy_send_after_block,
)
from app.services.handoff.identity import resolve_person
from app.services.handoff.ownership import (
    ActorType,
    InvalidTransition,
    OwnershipState,
    confirm_suppression,
    outbound_allowed,
    pause_confirmation_missing,
    pause_sla_breached,
    register_manual_pause,
    register_manual_reactivation,
    transition_ownership,
    uncontained_exposure,
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SP = ZoneInfo("America/Sao_Paulo")
T0 = datetime(2026, 8, 12, 10, 0, tzinfo=SP)  # quarta, meio do expediente

_ULID_BASE = "01J8ZM7WVX2Q9RKTHB3F6D5D"
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _ulid(n):
    return _ULID_BASE + _ALPHABET[n // 32] + _ALPHABET[n % 32]


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


def _link(session, tenant_id, *, email="pessoa.sintetica@example.com", external_id=None,
          requested_at=T0) -> CrmLeadLink:
    person_id = resolve_person(session, tenant_id, email, None).identity.id if email else None
    link = CrmLeadLink(
        tenant_id=tenant_id,
        source_system="rumy",
        external_lead_id=external_id or f"lead-sintetico-{uuid.uuid4().hex[:8]}",
        person_identity_id=person_id,
    )
    session.add(link)
    session.flush()
    transition_ownership(
        session, link, OwnershipState.HANDOFF_REQUESTED, ActorType.PROVIDER_EVENT,
        now=requested_at,
    )
    return link


def _envelope(n, lead, email="pessoa.sintetica@example.com", occurred=None):
    return {
        "schema_version": "1.1",
        "event_id": _ulid(n),
        "event_type": "handoff.requested",
        "occurred_at": (occurred or datetime(2026, 8, 12, 13, 0, tzinfo=SP)).isoformat(),
        "external_lead_id": lead,
        "person": {"full_name": "Pessoa Sintética [QA]",
                   "email": {"status": "known", "value": email}},
        "company": {"name": {"status": "known", "value": "Empresa Sintética QA Ltda"}},
        "reason": "positive_reply",
    }


# ── alerta ───────────────────────────────────────────────────────────────────

def test_alerta_duplicado_por_retry_e_deduplicado(session, tenant_id, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "HANDOFF_APPLY_ENABLED", True)
    payload = _envelope(0, "lead-alerta")
    row, _ = persist_raw_event(session, tenant_id, json.dumps(payload).encode(), payload)
    out = process_raw_event(session, row.id)
    assert out["status"] == "applied"
    # alerta primário registrado uma vez
    alerts = (
        session.query(CrmStateTransition)
        .filter_by(axis="alert", to_state="pause_alert_raised")
        .all()
    )
    assert len(alerts) == 1
    # retry do mesmo evento (bytes diferentes) → duplicate no negócio → sem 2º alerta
    row2, _ = persist_raw_event(
        session, tenant_id, json.dumps(payload, indent=2).encode(), payload
    )
    process_raw_event(session, row2.id)
    assert (
        session.query(CrmStateTransition)
        .filter_by(axis="alert", to_state="pause_alert_raised")
        .count()
        == 1
    )


def test_dois_handoffs_simultaneos_mesma_pessoa(session, tenant_id):
    a = _link(session, tenant_id, external_id="lead-sim-A")
    b = _link(session, tenant_id, external_id="lead-sim-B")
    r1 = raise_pause_alert(session, a)
    r2 = raise_pause_alert(session, b)
    assert r1["raised"] and r2["raised"]  # um alerta por lead, sem colisão
    assert outbound_allowed(session, a)[0] is False
    assert outbound_allowed(session, b)[0] is False


def test_novo_lead_mesma_pessoa_com_pausa_pendente(session, tenant_id):
    _link(session, tenant_id, external_id="lead-pend-A")
    novo = CrmLeadLink(
        tenant_id=tenant_id, source_system="rumy", external_lead_id="lead-pend-B",
        person_identity_id=resolve_person(
            session, tenant_id, "pessoa.sintetica@example.com", None
        ).identity.id,
    )
    session.add(novo)
    session.flush()
    assert outbound_allowed(session, novo) == (False, "person_protected")


# ── pausa manual (DEC-8) ─────────────────────────────────────────────────────

def test_pausa_sem_ator_e_sem_evidencia_recusadas(session, tenant_id):
    link = _link(session, tenant_id)
    with pytest.raises(InvalidTransition, match="ator"):
        register_manual_pause(session, link, "", "pausei no painel")
    with pytest.raises(InvalidTransition, match="evidência"):
        register_manual_pause(session, link, "ana.qa", "   ")
    assert link.automation_state == "SUPPRESSION_REQUESTED"  # nada mudou


def test_manually_confirmed_distinto_de_confirmed(session, tenant_id):
    link = _link(session, tenant_id)
    register_manual_pause(
        session, link, "ana.qa", "pausei a cadência do contato no painel do Rumy às 10:03",
        now=T0 + timedelta(minutes=3),
    )
    assert link.automation_state == "MANUALLY_CONFIRMED"
    assert link.automation_state != "SUPPRESSION_CONFIRMED"
    # confirmação técnica não é alcançável a partir de MANUALLY_CONFIRMED
    with pytest.raises(InvalidTransition):
        confirm_suppression(session, link)
    # trilha administrativa com ator
    audit = session.query(AdminAuditLog).filter_by(action="handoff.manual_pause").one()
    assert audit.actor_email == "ana.qa"
    assert audit.target_id == str(link.id)
    # snapshot separa os dois estados
    snap = local_snapshot(session, tenant_id)
    assert snap["links_by_automation"].get("MANUALLY_CONFIRMED") == 1
    assert "SUPPRESSION_CONFIRMED" not in snap["links_by_automation"]


def test_pausa_nao_religa_outbound(session, tenant_id):
    link = _link(session, tenant_id)
    register_manual_pause(session, link, "ana.qa", "pausa registrada [QA]")
    assert outbound_allowed(session, link)[0] is False  # nada no C religa


# ── três relógios (DEC-6) ────────────────────────────────────────────────────

def test_pausa_4min_ownership_20min(session, tenant_id):
    """Pausa dentro do SLA; assunção estourada — relógios separados."""
    link = _link(session, tenant_id)
    register_manual_pause(session, link, "ana.qa", "pausa [QA]", now=T0 + timedelta(minutes=4))
    assert pause_sla_breached(link, now=T0 + timedelta(minutes=20)) is False
    from app.services.handoff.ownership import accept_sla_breached

    assert accept_sla_breached(link, now=T0 + timedelta(minutes=20)) is True


def test_ownership_3min_pausa_8min_estoura_pausa(session, tenant_id):
    """Assunção rápida NÃO contém a exposição: pausa é o relógio crítico."""
    link = _link(session, tenant_id)
    transition_ownership(
        session, link, OwnershipState.HUMAN_OWNED, ActorType.HUMAN, actor_ref="ana",
        now=T0 + timedelta(minutes=3),
    )
    # 8 min sem pausa registrada: relógio de pausa estourado MESMO com HUMAN_OWNED
    assert pause_sla_breached(link, now=T0 + timedelta(minutes=8)) is True
    assert pause_confirmation_missing(link) is True  # situação crítica, não sucesso
    snap = local_snapshot(session, tenant_id)
    assert snap["handoffs_without_pause_confirmation"] == 1
    assert snap["pause_confirmation_missing_critical"] is True


def test_ninguem_pausa_escalona_e_marca_nao_contida(session, tenant_id):
    link = _link(session, tenant_id)
    # 6 min úteis: estoura SLA → escalona (nível 1)
    r1 = escalate_overdue(session, now=T0 + timedelta(minutes=6))
    assert r1["escalated"] == 1 and r1["uncontained"] == 0
    # 11 min úteis (>2×SLA): exposição não contida (nível 2) — idempotente
    r2 = escalate_overdue(session, now=T0 + timedelta(minutes=11))
    assert r2["uncontained"] == 1
    r3 = escalate_overdue(session, now=T0 + timedelta(minutes=15))
    assert r3["uncontained"] == 0  # já marcado, não duplica
    assert uncontained_exposure(link, now=T0 + timedelta(minutes=12)) is True
    # e o lead JAMAIS volta à automação por timeout
    assert link.ownership_state == "HANDOFF_REQUESTED"
    assert outbound_allowed(session, link)[0] is False
    snap = local_snapshot(session, tenant_id)
    assert snap["uncontained_exposure_count"] >= 1


def test_ninguem_assume_permanece_protegido(session, tenant_id):
    link = _link(session, tenant_id)
    register_manual_pause(session, link, "ana.qa", "pausa [QA]", now=T0 + timedelta(minutes=2))
    # pausado e abandonado: seguro, só atrasado — escala pelo relógio de aceite
    from app.services.handoff.ownership import accept_sla_breached

    assert accept_sla_breached(link, now=T0 + timedelta(hours=2)) is True
    assert link.ownership_state == "HANDOFF_REQUESTED"
    assert outbound_allowed(session, link)[0] is False


# ── reativação (§9) ──────────────────────────────────────────────────────────

def test_reativacao_sem_evidencia_recusada(session, tenant_id):
    link = _link(session, tenant_id)
    register_manual_pause(session, link, "ana.qa", "pausa [QA]")
    transition_ownership(session, link, OwnershipState.HUMAN_OWNED, ActorType.HUMAN, actor_ref="ana")
    transition_ownership(session, link, OwnershipState.RELEASED, ActorType.HUMAN,
                         reason="devolvido [QA]")
    with pytest.raises(InvalidTransition, match="evidência"):
        register_manual_reactivation(session, link, "ana.qa", "")
    assert link.ownership_state == "RELEASED"
    assert outbound_allowed(session, link)[0] is False


def test_reativacao_com_evidencia_religa(session, tenant_id):
    link = _link(session, tenant_id)
    register_manual_pause(session, link, "ana.qa", "pausa [QA]")
    transition_ownership(session, link, OwnershipState.HUMAN_OWNED, ActorType.HUMAN, actor_ref="ana")
    transition_ownership(session, link, OwnershipState.RELEASED, ActorType.HUMAN,
                         reason="devolvido [QA]")
    register_manual_reactivation(
        session, link, "ana.qa", "reativei a cadência no painel do Rumy às 14:22 [QA]"
    )
    assert link.ownership_state == "AUTOMATED"
    assert link.automation_state == "ACTIVE"
    assert outbound_allowed(session, link) == (True, "ok")
    assert session.query(AdminAuditLog).filter_by(action="handoff.manual_reactivation").count() == 1


def test_released_jamais_religa_sozinho(session, tenant_id):
    link = _link(session, tenant_id)
    transition_ownership(session, link, OwnershipState.HUMAN_OWNED, ActorType.HUMAN, actor_ref="ana")
    transition_ownership(session, link, OwnershipState.RELEASED, ActorType.HUMAN,
                         reason="devolvido [QA]")
    for actor in (ActorType.SYSTEM, ActorType.PROVIDER_EVENT):
        with pytest.raises(InvalidTransition):
            transition_ownership(session, link, OwnershipState.AUTOMATED, actor, reason="auto")
    assert outbound_allowed(session, link)[0] is False


def test_evento_antigo_nao_remove_protecao(session, tenant_id, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "HANDOFF_APPLY_ENABLED", True)
    novo = _envelope(1, "lead-antigo", occurred=datetime(2026, 8, 12, 13, 0, tzinfo=SP))
    row, _ = persist_raw_event(session, tenant_id, json.dumps(novo).encode(), novo)
    process_raw_event(session, row.id)
    antigo = _envelope(2, "lead-antigo", occurred=datetime(2026, 8, 12, 9, 0, tzinfo=SP))
    row2, _ = persist_raw_event(session, tenant_id, json.dumps(antigo).encode(), antigo)
    out = process_raw_event(session, row2.id)
    assert out["status"] == "superseded"
    link = session.query(CrmLeadLink).filter_by(external_lead_id="lead-antigo").one()
    assert link.ownership_state == "HANDOFF_REQUESTED"  # proteção intacta


# ── DEC-7 e métrica UNOBSERVABLE ─────────────────────────────────────────────

def test_unknown_capability_e_nao_unsupported():
    assert RUMY_SUPPRESSION_CAPABILITY == ProviderCapability.UNKNOWN_CAPABILITY
    # silêncio nunca produz UNSUPPORTED — guard estrutural
    with pytest.raises(ValueError, match="silêncio"):
        declare_capability(ProviderCapability.UNSUPPORTED)
    ok = declare_capability(
        ProviderCapability.UNSUPPORTED, evidence_ref="resposta do fornecedor 2026-08-14"
    )
    assert ok == ProviderCapability.UNSUPPORTED


def test_dashboard_nao_transforma_unobservable_em_zero(session, tenant_id):
    metric = rumy_send_after_block()
    assert isinstance(metric, UnobservableMetric)
    assert metric.display() == "NÃO OBSERVÁVEL"
    with pytest.raises(MetricNotObservable, match="não é zero"):
        _ = metric.value
    with pytest.raises(MetricNotObservable):
        int(metric)
    with pytest.raises(MetricNotObservable):
        float(metric)
    assert (metric == 0) is False  # comparação com zero nunca é verdadeira
    snap = local_snapshot(session, tenant_id)
    assert isinstance(snap["rumy_send_after_block"], UnobservableMetric)
    assert snap["rumy_suppression_capability"] == "UNKNOWN_CAPABILITY"
    assert snap["business_calendar_version"] == "weekday_only_v1"
    assert snap["holidays_supported"] is False
