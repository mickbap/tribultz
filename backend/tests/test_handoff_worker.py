"""Round 5 — campanha QA do F2: worker/inbox (adapter → contrato → domínio).

Ataques da seção 8: persistência concluída + worker falha, adapter com exceção,
payload sem obrigatórios, shadow mode, reprocesso idempotente, mesmo timestamp,
mesma pessoa sob novo external_lead_id, mesmo external_lead_id entre tenants.
Dados 100% sintéticos.
"""

import json
import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.auth import Tenant
from app.models.crm_handoff import CrmLeadEvent, CrmLeadLink
from app.services.handoff.adapter import RumyAdapter
from app.services.handoff.inbox import ProcessingError, persist_raw_event, process_raw_event
from app.services.handoff.ownership import outbound_allowed

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_ULID_BASE = "01J8ZM7WVX2Q9RKTHB3F6D5B"
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _ulid(n: int) -> str:
    return _ULID_BASE + _ALPHABET[n // 32] + _ALPHABET[n % 32]


T0 = "2026-08-12T12:00:00+00:00"


def _envelope(n=0, *, lead="lead-sintetico-001", email="pessoa.sintetica@example.test",
              occurred=T0) -> dict:
    return {
        "schema_version": "1.1",
        "event_id": _ulid(n),
        "event_type": "handoff.requested",
        "occurred_at": occurred,
        "external_lead_id": lead,
        "person": {
            "full_name": "Pessoa Sintética [QA]",
            "email": {"status": "known", "value": email},
        },
        "company": {"name": {"status": "known", "value": "Empresa Sintética QA Ltda"}},
        "reason": "positive_reply",
    }


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


@pytest.fixture(name="apply_on")
def apply_on_fixture(monkeypatch):
    monkeypatch.setattr(settings, "HANDOFF_APPLY_ENABLED", True)


def _persist(session, tenant_id, payload: dict) -> CrmLeadEvent:
    body = json.dumps(payload).encode()
    row, created = persist_raw_event(session, tenant_id, body, payload)
    assert created
    return row


def test_shadow_mode_persiste_sem_aplicar(session, tenant_id):
    """HANDOFF_APPLY_ENABLED=False (default): ledger sim, domínio não."""
    assert settings.HANDOFF_APPLY_ENABLED is False
    row = _persist(session, tenant_id, _envelope(0))
    out = process_raw_event(session, row.id)  # type: ignore[arg-type]
    assert out["detail"] == "shadow_mode"
    assert row.status == "received"  # type: ignore[misc]
    assert session.query(CrmLeadLink).count() == 0  # nada aplicado


def test_pipeline_completo_sintetico(session, tenant_id, apply_on):
    row = _persist(session, tenant_id, _envelope(1))
    out = process_raw_event(session, row.id)  # type: ignore[arg-type]
    assert out["status"] == "applied" and out["detail"] == "transitioned"
    assert row.status == "applied"  # type: ignore[misc]
    assert row.external_lead_id == "lead-sintetico-001"  # sentinela substituída  # type: ignore[misc]
    link = session.query(CrmLeadLink).one()
    assert link.ownership_state == "HANDOFF_REQUESTED"
    # linha de negócio canônica existe e é apontada
    business = session.get(CrmLeadEvent, uuid.UUID(out["business_ledger_id"]))
    assert business.idempotency_key.startswith("prov:rumy:")


def test_reprocesso_e_noop(session, tenant_id, apply_on):
    row = _persist(session, tenant_id, _envelope(2))
    process_raw_event(session, row.id)  # type: ignore[arg-type]
    again = process_raw_event(session, row.id)  # type: ignore[arg-type]
    assert again["detail"] == "already_processed"


def test_mesmo_evento_bytes_diferentes_morre_na_chave_de_negocio(session, tenant_id, apply_on):
    """Reentrega com whitespace diferente passa pelo transporte, morre no negócio."""
    payload = _envelope(3)
    row1 = _persist(session, tenant_id, payload)
    process_raw_event(session, row1.id)  # type: ignore[arg-type]

    body2 = json.dumps(payload, indent=2).encode()  # bytes diferentes, evento igual
    row2, created = persist_raw_event(session, tenant_id, body2, payload)
    assert created  # transporte não pega (hash difere)
    out = process_raw_event(session, row2.id)  # type: ignore[arg-type]
    assert out["status"] == "duplicate"  # negócio pega (prov:rumy:<event_id>)
    assert row2.status == "duplicate"  # type: ignore[misc]
    assert session.query(CrmLeadLink).count() == 1  # um único handoff lógico


def test_payload_sem_obrigatorios_quarentena(session, tenant_id, apply_on):
    payload = _envelope(4)
    del payload["person"]  # sem pessoa: contrato rejeita
    row = _persist(session, tenant_id, payload)
    out = process_raw_event(session, row.id)  # type: ignore[arg-type]
    assert out["status"] == "quarantined"
    assert row.status == "quarantined"  # type: ignore[misc]
    assert "person" in (row.error or "")
    assert session.query(CrmLeadLink).count() == 0


def test_evento_nao_mapeado_audita_sem_efeito(session, tenant_id, apply_on):
    """'Rumy = Qualificado' (ou qualquer tipo não mapeado) só audita — zero efeito."""
    row = _persist(session, tenant_id, {"event_type": "rumy.qualificado", "lead": "x"})
    out = process_raw_event(session, row.id)  # type: ignore[arg-type]
    assert out["status"] == "unmapped"
    assert row.event_type_raw == "rumy.qualificado"  # type: ignore[misc]
    assert session.query(CrmLeadLink).count() == 0


def test_adapter_com_excecao_marca_failed_e_retenta(session, tenant_id, apply_on):
    """Persistência concluída + worker falha: linha 'failed', retry reprocessa."""

    class ExplodingAdapter(RumyAdapter):
        version = "exploding-qa"

        def to_handoff_event(self, raw):
            raise RuntimeError("falha transitória sintética")

    row = _persist(session, tenant_id, _envelope(5))
    with pytest.raises(ProcessingError):
        process_raw_event(session, row.id, adapter=ExplodingAdapter())  # type: ignore[arg-type]
    assert row.status == "failed"  # type: ignore[misc]
    assert "falha transitória sintética" in row.error

    # retry (agora com o adapter são) reprocessa a partir de 'failed'
    out = process_raw_event(session, row.id)  # type: ignore[arg-type]
    assert out["status"] == "applied"


def test_mesmo_timestamp_nao_reaplica(session, tenant_id, apply_on):
    """Dois eventos distintos com o MESMO occurred_at: o segundo é superseded
    (regra 'só aplica se estritamente mais novo' — empate não regride nem duplica)."""
    r1 = _persist(session, tenant_id, _envelope(6))
    process_raw_event(session, r1.id)  # type: ignore[arg-type]
    r2 = _persist(session, tenant_id, _envelope(7))  # event_id difere, occurred igual
    out = process_raw_event(session, r2.id)  # type: ignore[arg-type]
    assert out["status"] == "superseded"


def test_evento_atrasado_superseded(session, tenant_id, apply_on):
    r1 = _persist(session, tenant_id, _envelope(8))
    process_raw_event(session, r1.id)  # type: ignore[arg-type]
    atrasado = _envelope(
        9, occurred=(datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc)).isoformat()
    )
    r2 = _persist(session, tenant_id, atrasado)
    out = process_raw_event(session, r2.id)  # type: ignore[arg-type]
    assert out["status"] == "superseded"


def test_mesma_pessoa_novo_external_lead_id(session, tenant_id, apply_on):
    r1 = _persist(session, tenant_id, _envelope(10, lead="lead-A"))
    process_raw_event(session, r1.id)  # type: ignore[arg-type]
    depois = (datetime(2026, 8, 12, 12, 5, tzinfo=timezone.utc)).isoformat()
    r2 = _persist(session, tenant_id, _envelope(11, lead="lead-B", occurred=depois))
    process_raw_event(session, r2.id)  # type: ignore[arg-type]
    links = session.query(CrmLeadLink).all()
    assert len(links) == 2
    assert len({link.person_identity_id for link in links}) == 1
    for link in links:
        assert outbound_allowed(session, link)[0] is False  # DEC-5 atravessa leads


def test_mesmo_external_lead_id_entre_tenants_isola(session, tenant_id, apply_on):
    other = Tenant(name=f"Tenant QA2 {uuid.uuid4().hex[:6]}", slug=f"tenant-qa2-{uuid.uuid4()}")
    session.add(other)
    session.flush()
    r1 = _persist(session, tenant_id, _envelope(12))
    process_raw_event(session, r1.id)  # type: ignore[arg-type]
    r2 = _persist(session, other.id, _envelope(13))
    process_raw_event(session, r2.id)  # type: ignore[arg-type]
    links = session.query(CrmLeadLink).all()
    assert len(links) == 2
    assert len({link.tenant_id for link in links}) == 2
    assert len({link.person_identity_id for link in links}) == 2  # pessoas por tenant


def test_pipeline_nao_conhece_attio_por_construcao():
    """'Backend persiste + Attio indisponível': o NÚCLEO do pipeline (trava,
    ownership, identidade, ingest, transporte) não referencia integrations/attio
    — indisponibilidade do Attio é estruturalmente irrelevante para a proteção.

    Exceção SANCIONADA (Round 7 §7): alerts.py cria a task operacional no Attio
    como parte do alerta do Caminho C — best-effort, import LAZY (dentro da
    função, atrás de try/except e de ATTIO_ENABLED). Attio fora do ar degrada o
    alerta, nunca a trava."""
    import pathlib

    base = pathlib.Path(__file__).resolve().parents[1] / "app"
    core = [
        p for p in (base / "services" / "handoff").glob("*.py")
        if p.name != "alerts.py"
    ] + [base / "routers" / "rumy.py", base / "tasks" / "task_k_rumy.py"]
    for f in core:
        assert "integrations.attio" not in f.read_text(), f"{f} referencia attio"
    # a borda sancionada: import de attio em alerts.py existe mas NUNCA no
    # nível de módulo (lazy = Attio indisponível não impede nem importar)
    alerts_src = (base / "services" / "handoff" / "alerts.py").read_text()
    toplevel_imports = [
        line for line in alerts_src.splitlines()
        if line.startswith(("import ", "from ")) and "attio" in line
    ]
    assert toplevel_imports == [], f"import de attio no topo de alerts.py: {toplevel_imports}"
    assert "from app.integrations.attio.tasks import" in alerts_src  # lazy, na função
