"""Round 4 F3: ingestão idempotente — replay, fora-de-ordem, quarentena, corrida.

Campanha QA §11: concorrência entre handoff.requested × novo lead × evento
duplicado × evento atrasado. DB real com rollback por teste; dados sintéticos.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models.auth import Tenant
from app.models.crm_handoff import CrmLeadEvent, CrmLeadLink, CrmStateTransition
from app.models.prospect_suppression import ProspectSuppression
from app.services.handoff.contract import (
    CompanyIdentityPayload,
    HandoffEvent,
    MaybeStr,
    PersonIdentityPayload,
)
from app.services.handoff.metrics import local_snapshot
from app.services.handoff.ownership import outbound_allowed
from app.services.handoff.service import ingest_handoff_event

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_ULID_BASE = "01J8ZM7WVX2Q9RKTHB3F6D5A"  # 24 chars; sufixo de 2 completa o ULID
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _ulid(n: int) -> str:
    return _ULID_BASE + _ALPHABET[n // 32] + _ALPHABET[n % 32]


T0 = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


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


def _event(n=0, *, lead="lead-sintetico-001", email="pessoa.sintetica@example.test",
           linkedin=None, occurred=T0, reason="positive_reply") -> HandoffEvent:
    person_kwargs = {"full_name": "Pessoa Sintética [QA]"}
    if email:
        person_kwargs["email"] = MaybeStr.known(email)  # type: ignore[arg-type]
    if linkedin:
        person_kwargs["linkedin_url"] = MaybeStr.known(linkedin)  # type: ignore[arg-type]
    return HandoffEvent(
        event_id=_ulid(n),
        occurred_at=occurred,
        external_lead_id=lead,
        person=PersonIdentityPayload(**person_kwargs),  # type: ignore[arg-type]
        company=CompanyIdentityPayload(name=MaybeStr.known("Empresa Sintética QA Ltda")),
        reason=reason,  # type: ignore[arg-type]
    )


def test_caminho_feliz_um_evento_um_handoff(session, tenant_id):
    result = ingest_handoff_event(session, tenant_id, _event(0))
    assert result.status == "applied" and result.detail == "transitioned"
    assert result.link.ownership_state == "HANDOFF_REQUESTED"  # type: ignore[misc]
    assert result.link.automation_state == "SUPPRESSION_REQUESTED"  # type: ignore[misc]
    assert result.link.person_identity_id is not None  # type: ignore[misc]
    assert result.ledger.applied_at is not None
    assert outbound_allowed(session, result.link)[0] is False  # type: ignore[arg-type]
    # espelho DEC-5 na lista dura de supressão
    assert (
        session.query(ProspectSuppression)
        .filter(ProspectSuppression.email == "pessoa.sintetica@example.test")
        .count()
        == 1
    )


def test_replay_n_vezes_produz_um_unico_handoff(session, tenant_id):
    first = ingest_handoff_event(session, tenant_id, _event(1))
    for _ in range(3):
        dup = ingest_handoff_event(session, tenant_id, _event(1))
        assert dup.status == "duplicate" and dup.detail == "duplicate"
    session.flush()
    assert dup.ledger.id == first.ledger.id  # type: ignore[misc]
    assert dup.ledger.attempts == 4  # type: ignore[misc]
    # efeitos únicos: 1 linha de ledger, 1 transição de ownership, 1 supressão
    assert session.query(CrmLeadEvent).filter_by(tenant_id=tenant_id).count() == 1
    transitions = (
        session.query(CrmStateTransition)
        .filter_by(lead_link_id=first.link.id, axis="ownership")  # type: ignore[misc]
        .count()
    )
    assert transitions == 1
    assert (
        session.query(ProspectSuppression)
        .filter(ProspectSuppression.email == "pessoa.sintetica@example.test")
        .count()
        == 1
    )


def test_mesmo_evento_payload_divergente_e_sinalizado(session, tenant_id):
    ingest_handoff_event(session, tenant_id, _event(2))
    divergente = ingest_handoff_event(session, tenant_id, _event(2, reason="manual_flag"))
    assert divergente.status == "duplicate"
    assert divergente.detail == "duplicate_divergent"
    assert divergente.ledger.processing_result["divergent_payload_hashes"]  # type: ignore[misc]


def test_evento_atrasado_nao_regride(session, tenant_id):
    novo = ingest_handoff_event(session, tenant_id, _event(3, occurred=T0))
    atrasado = ingest_handoff_event(
        session, tenant_id, _event(4, occurred=T0 - timedelta(hours=2))
    )
    assert atrasado.status == "superseded" and atrasado.detail == "out_of_order"
    assert novo.link.ownership_state == "HANDOFF_REQUESTED"  # type: ignore[misc]
    assert novo.link.last_applied_event_id == novo.ledger.id  # o atrasado não vira "último"  # type: ignore[misc]


def test_minimo_ausente_vai_para_quarentena_sem_link(session, tenant_id):
    sem_chave = _event(5, email=None)  # type: ignore[arg-type]
    result = ingest_handoff_event(session, tenant_id, sem_chave)
    assert result.status == "quarantined"
    assert result.link is None
    assert session.query(CrmLeadLink).filter_by(tenant_id=tenant_id).count() == 0
    assert result.ledger.processing_result == {"detail": "identity_minimum_missing"}  # type: ignore[misc]


def test_dec5_nova_campanha_novo_lead_mesma_pessoa(session, tenant_id):
    """Concorrência da campanha §11: handoff.requested × novo external_lead_id."""
    ingest_handoff_event(session, tenant_id, _event(6, lead="lead-campanha-A"))
    segundo = ingest_handoff_event(
        session, tenant_id,
        _event(7, lead="lead-campanha-B", occurred=T0 + timedelta(minutes=5)),
    )
    # o novo lead ganha seu próprio handoff (sinal real), e a pessoa segue protegida
    assert segundo.status == "applied"
    links = session.query(CrmLeadLink).filter_by(tenant_id=tenant_id).all()
    assert len(links) == 2
    assert len({link.person_identity_id for link in links}) == 1  # mesma pessoa
    for link in links:
        assert outbound_allowed(session, link)[0] is False


def test_conflito_de_identidade_via_evento(session, tenant_id):
    ingest_handoff_event(
        session, tenant_id,
        _event(8, lead="lead-a", email="pessoa.a@example.test", linkedin="in/pessoa-a-qa"),
    )
    ingest_handoff_event(
        session, tenant_id,
        _event(9, lead="lead-b", email="pessoa.b@example.test", linkedin="in/pessoa-b-qa",
               occurred=T0 + timedelta(minutes=1)),
    )
    conflitante = ingest_handoff_event(
        session, tenant_id,
        _event(10, lead="lead-c", email="pessoa.a@example.test", linkedin="in/pessoa-b-qa",
               occurred=T0 + timedelta(minutes=2)),
    )
    assert conflitante.status == "applied"
    assert conflitante.link.identity_conflict is True  # type: ignore[misc]
    assert conflitante.link.person_identity_id is None  # sem merge silencioso  # type: ignore[misc]
    assert outbound_allowed(session, conflitante.link) == (False, "identity_conflict")  # type: ignore[arg-type]


def test_corrida_unique_constraint_decide(session, tenant_id):
    result = ingest_handoff_event(session, tenant_id, _event(11))
    clone = CrmLeadEvent(
        tenant_id=tenant_id,
        source_system="rumy",
        external_lead_id="lead-sintetico-001",
        idempotency_key=result.ledger.idempotency_key,
        schema_version="1.1",
        event_type="handoff.requested",
        payload_hash="deadbeef",
    )
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.add(clone)
            session.flush()
    # o vencedor permanece íntegro
    assert session.query(CrmLeadEvent).filter_by(
        idempotency_key=result.ledger.idempotency_key
    ).count() == 1


def test_closed_nao_reabre_por_evento_de_provedor(session, tenant_id):
    primeiro = ingest_handoff_event(session, tenant_id, _event(12))
    primeiro.link.ownership_state = "CLOSED"  # type: ignore[assignment, misc]
    session.flush()
    sinal = ingest_handoff_event(
        session, tenant_id, _event(13, occurred=T0 + timedelta(hours=1))
    )
    assert sinal.status == "applied" and sinal.detail == "closed_requires_human"
    assert sinal.link.ownership_state == "CLOSED"  # type: ignore[misc]


def test_metrics_nao_declara_zero_sem_instrumento(session, tenant_id):
    """Round 4 §5: ausência de evidência ≠ zero."""
    ingest_handoff_event(session, tenant_id, _event(14))
    snap = local_snapshot(session, tenant_id)
    assert snap["links_by_ownership"] == {"HANDOFF_REQUESTED": 1}
    assert snap["protected_persons"] == 1
    assert "UNOBSERVABLE" in snap["rumy_send_after_block"]
