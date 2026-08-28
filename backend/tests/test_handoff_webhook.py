"""Round 5 — campanha QA do F2: o receptor do webhook Rumy.

Ataques de transporte: flag off, assinatura inválida, secret ausente, corpo
não-JSON, reentrega. O broker é mockado (delay) — worker é testado à parte em
test_handoff_worker.py. Dados 100% sintéticos.

Round 16-G (#689): ``_sign`` passou a produzir o contrato REAL do fornecedor
(Base64 sobre ``{timestamp}.{rawBody}`` + carimbo). A fixture se adaptou ao
contrato — o contrato nunca se adapta à fixture.
"""

import hashlib
import json
import os
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.auth import Tenant
from app.models.crm_handoff import CrmLeadEvent

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SECRET = "segredo-sintetico-qa"


@pytest.fixture(name="session")
def session_fixture():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(name="client")
def client_fixture(session, monkeypatch):
    def get_db_override():
        yield session

    app.dependency_overrides[get_db] = get_db_override
    # o commit do router não pode fechar a transação-envelope do teste
    monkeypatch.setattr(session, "commit", session.flush)
    # broker fora do jogo: delay vira no-op contável
    calls = []
    monkeypatch.setattr(
        "app.tasks.task_k_rumy.process_rumy_event.delay", lambda *a, **k: calls.append(a)
    )
    client = TestClient(app)
    client.delay_calls = calls
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="tenant_id")
def tenant_fixture(session):
    tenant = Tenant(name=f"Tenant QA {uuid.uuid4().hex[:6]}", slug=f"tenant-qa-{uuid.uuid4()}")
    session.add(tenant)
    session.flush()
    return tenant.id


@pytest.fixture(name="enabled")
def enabled_fixture(monkeypatch, tenant_id):
    monkeypatch.setattr(settings, "RUMY_WEBHOOK_ENABLED", True)
    monkeypatch.setattr(settings, "RUMY_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(settings, "HANDOFF_TENANT_ID", str(tenant_id))


def _sign(body: bytes, secret: str = SECRET, ts: str | None = None) -> dict:
    """Headers do contrato público do Rumy (#689)."""
    from app.services.handoff.webhook_auth import expected_signature

    ts = ts or str(int(time.time()))
    return {
        "X-Rumy-Signature": expected_signature(ts, body, secret),
        "X-Rumy-Timestamp": ts,
        "X-Rumy-Event-Id": f"evt_{uuid.uuid4()}",
    }


BODY = json.dumps({"event_type": "sintetico.qa", "id": "lead-sintetico-001"}).encode()


def test_flag_off_endpoint_inexistente(client):
    # default OFF: superfície externa zero — nem 401, simplesmente não existe
    assert settings.RUMY_WEBHOOK_ENABLED is False
    r = client.post("/api/v1/webhooks/rumy", content=BODY, headers=_sign(BODY))
    assert r.status_code == 404


def test_tenant_nao_configurado_fail_closed(client, monkeypatch):
    monkeypatch.setattr(settings, "RUMY_WEBHOOK_ENABLED", True)
    monkeypatch.setattr(settings, "RUMY_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(settings, "HANDOFF_TENANT_ID", "")
    r = client.post("/api/v1/webhooks/rumy", content=BODY, headers=_sign(BODY))
    assert r.status_code == 503


def test_secret_ausente_rejeita_tudo(client, monkeypatch, tenant_id):
    monkeypatch.setattr(settings, "RUMY_WEBHOOK_ENABLED", True)
    monkeypatch.setattr(settings, "RUMY_WEBHOOK_SECRET", "")
    monkeypatch.setattr(settings, "HANDOFF_TENANT_ID", str(tenant_id))
    r = client.post("/api/v1/webhooks/rumy", content=BODY, headers=_sign(BODY))
    assert r.status_code == 401


def test_assinatura_invalida_nada_persiste(client, session, enabled):
    r = client.post(
        "/api/v1/webhooks/rumy", content=BODY, headers=_sign(BODY, secret="outro-segredo")
    )
    assert r.status_code == 401
    assert session.query(CrmLeadEvent).count() == 0


def test_assinatura_valida_persiste_bruto_e_enfileira(client, session, enabled):
    r = client.post("/api/v1/webhooks/rumy", content=BODY, headers=_sign(BODY))
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"
    row = session.query(CrmLeadEvent).one()
    assert row.status == "received"
    assert row.payload_raw == json.loads(BODY)
    # #689: a chave primária de idempotência passou a ser o Event ID do produtor
    assert row.idempotency_key.startswith("evt:")
    assert row.provider_event_id
    assert len(client.delay_calls) == 1  # worker enfileirado


def test_reentrega_mesmo_event_id_deduplicada(client, session, enabled):
    """Retry do Rumy: MESMO Event ID (até 7×). A dedupe é por ele, não por bytes."""
    h = _sign(BODY)
    client.post("/api/v1/webhooks/rumy", content=BODY, headers=h)
    r2 = client.post("/api/v1/webhooks/rumy", content=BODY, headers=h)
    assert r2.json()["status"] == "duplicate"
    row = session.query(CrmLeadEvent).one()  # uma linha só
    assert row.attempts == 2
    assert len(client.delay_calls) == 1  # reentrega não re-enfileira


def test_corpo_nao_json_autenticado_e_preservado(client, session, enabled):
    body = b"isto nao e json {"
    r = client.post("/api/v1/webhooks/rumy", content=body, headers=_sign(body))
    assert r.status_code == 200
    row = session.query(CrmLeadEvent).one()
    assert row.payload_raw["_non_json_body"] is True
    assert row.payload_raw["sha256"] == hashlib.sha256(body).hexdigest()
