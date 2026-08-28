"""#689 — o receptor contra o contrato PÚBLICO do Rumy (Round 16-G).

Cobre as bordas que o esquema provisório do Round 5 não tinha: Base64 (não
hexdigest), assinatura sobre ``{timestamp}.{rawBody}`` (não só o corpo), janela
de ±5 min e idempotência pelo Event ID.

Guard permanente: os testes de esquema antigo abaixo DEVEM continuar recebendo
401. Se algum dia passarem, alguém relaxou a autenticação para uma fixture
passar — que é exatamente o que a ordem do round proibiu.

Dados 100% sintéticos. Nenhuma flag é habilitada fora do escopo do teste.
"""

import base64
import hashlib
import hmac
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
from app.services.handoff.webhook_auth import MAX_SKEW_SECONDS, expected_signature

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SECRET = "segredo-sintetico-689"
EVENT_ID = "evt_sintetico_693"
BODY = json.dumps({"event_type": "lead.converted", "id": EVENT_ID}).encode()
URL = "/api/v1/webhooks/rumy"


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
    monkeypatch.setattr(session, "commit", session.flush)
    monkeypatch.setattr(
        "app.tasks.task_k_rumy.process_rumy_event.delay", lambda *a, **k: None
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(name="enabled")
def enabled_fixture(session, monkeypatch):
    tenant = Tenant(name=f"T689 {uuid.uuid4().hex[:6]}", slug=f"t689-{uuid.uuid4()}")
    session.add(tenant)
    session.flush()
    monkeypatch.setattr(settings, "RUMY_WEBHOOK_ENABLED", True)
    monkeypatch.setattr(settings, "RUMY_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(settings, "HANDOFF_TENANT_ID", str(tenant.id))


def _headers(body=BODY, ts=None, event_id=None, secret=SECRET):
    """Por padrão o Event ID espelha o ``id`` do corpo (binding do #693)."""
    ts = ts or str(int(time.time()))
    if event_id is None:
        try:
            event_id = str(json.loads(body)["id"])
        except Exception:
            event_id = f"evt_{uuid.uuid4()}"
    return {
        "X-Rumy-Signature": expected_signature(ts, body, secret),
        "X-Rumy-Timestamp": ts,
        "X-Rumy-Event-Id": event_id,
        "X-Rumy-Event-Type": "lead.converted",
    }


class TestEsquemaDeAssinatura:
    def test_contrato_real_aceito(self, client, enabled):
        assert client.post(URL, content=BODY, headers=_headers()).status_code == 200

    def test_esquema_antigo_hexdigest_rejeitado(self, client, enabled):
        """Round 5 assinava hexdigest do corpo. Tem de morrer com 401."""
        ts = str(int(time.time()))
        sig = hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()
        r = client.post(
            URL, content=BODY, headers={"X-Rumy-Signature": sig, "X-Rumy-Timestamp": ts}
        )
        assert r.status_code == 401

    def test_assinatura_só_do_corpo_sem_timestamp_rejeitada(self, client, enabled):
        """Base64 correto, mas sem a concatenação {timestamp}. — 401."""
        ts = str(int(time.time()))
        sig = base64.b64encode(
            hmac.new(SECRET.encode(), BODY, hashlib.sha256).digest()
        ).decode()
        r = client.post(
            URL, content=BODY, headers={"X-Rumy-Signature": sig, "X-Rumy-Timestamp": ts}
        )
        assert r.status_code == 401

    def test_secret_errado_rejeitado(self, client, enabled):
        r = client.post(URL, content=BODY, headers=_headers(secret="outro-segredo"))
        assert r.status_code == 401

    def test_corpo_adulterado_apos_assinar_rejeitado(self, client, enabled):
        h = _headers(BODY)
        r = client.post(URL, content=BODY + b" ", headers=h)
        assert r.status_code == 401


class TestJanelaTemporal:
    def test_carimbo_antigo_e_replay_rejeitado(self, client, enabled):
        velho = str(int(time.time()) - MAX_SKEW_SECONDS - 60)
        r = client.post(URL, content=BODY, headers=_headers(ts=velho))
        assert r.status_code == 401, "assinatura válida fora da janela tem de ser recusada"

    def test_carimbo_no_futuro_rejeitado(self, client, enabled):
        futuro = str(int(time.time()) + MAX_SKEW_SECONDS + 60)
        assert client.post(URL, content=BODY, headers=_headers(ts=futuro)).status_code == 401

    def test_dentro_da_janela_aceito(self, client, enabled):
        quase = str(int(time.time()) - MAX_SKEW_SECONDS + 30)
        assert client.post(URL, content=BODY, headers=_headers(ts=quase)).status_code == 200

    def test_carimbo_ausente_rejeitado(self, client, enabled):
        h = _headers()
        del h["X-Rumy-Timestamp"]
        assert client.post(URL, content=BODY, headers=h).status_code == 401

    def test_carimbo_nao_numerico_rejeitado(self, client, enabled):
        r = client.post(URL, content=BODY, headers=_headers(ts="2026-08-28T13:00:00Z"))
        assert r.status_code == 401


class TestIdempotenciaPorEventId:
    def test_retry_identico_e_duplicate(self, client, session, enabled):
        """Mesmo Event ID + mesmo hash = retry idempotente."""
        client.post(URL, content=BODY, headers=_headers())
        r2 = client.post(URL, content=BODY, headers=_headers())
        assert r2.status_code == 200 and r2.json()["status"] == "duplicate"
        row = session.query(CrmLeadEvent).one()
        assert int(row.attempts) == 2
        assert str(row.provider_event_id) == EVENT_ID

    def test_mesmo_event_id_hash_diferente_e_conflito_409(self, client, session, enabled):
        """Mesmo ID + hash diferente = conflito de integridade. Nem substitui, nem cala."""
        b1 = json.dumps({"id": EVENT_ID, "a": 1}).encode()
        b2 = json.dumps({"id": EVENT_ID, "a": 2}).encode()
        client.post(URL, content=b1, headers=_headers(b1))
        r2 = client.post(URL, content=b2, headers=_headers(b2))

        assert r2.status_code == 409, "divergência não pode virar 200 silencioso"
        row = session.query(CrmLeadEvent).one()
        # corpo original intacto: o divergente não substitui nem reprocessa
        assert str(row.payload_hash) == hashlib.sha256(b1).hexdigest()
        assert int(row.attempts) == 2


class TestFlagsPermanecemOff:
    def test_defaults_do_settings_continuam_off(self):
        """Nada neste round liga superfície externa."""
        from app.config import Settings

        for flag in ("RUMY_WEBHOOK_ENABLED", "HANDOFF_APPLY_ENABLED", "ATTIO_ENABLED"):
            assert Settings.model_fields[flag].default is False, flag
