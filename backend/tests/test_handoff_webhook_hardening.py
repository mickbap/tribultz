"""#693 hardening (Round 16-J) — testes ADVERSARIAIS da fronteira Rumy.

Cada classe corresponde a um achado da auditoria 16-H ou a um item da ordem.
Todos são testes de recusa: provam que a fronteira falha FECHADA.

Regra que estes testes protegem: entrada malformada nunca vira 500. Um 500 na
autenticação transforma lixo do atacante em sinal para ele.

Dados 100% sintéticos. Nenhuma flag habilitada fora do escopo de cada teste.
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
from app.services.handoff.webhook_auth import (
    MAX_PROVIDER_EVENT_ID,
    expected_signature,
    is_valid_event_id,
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SECRET = "segredo-sintetico-16j"
URL = "/api/v1/webhooks/rumy"
EVENT_ID = "evt_16j_sintetico"
BODY = json.dumps({"event_type": "lead.converted", "id": EVENT_ID}).encode()


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
    monkeypatch.setattr("app.tasks.task_k_rumy.process_rumy_event.delay", lambda *a, **k: None)
    tenant = Tenant(name=f"T16J {uuid.uuid4().hex[:6]}", slug=f"t16j-{uuid.uuid4()}")
    session.add(tenant)
    session.flush()
    monkeypatch.setattr(settings, "RUMY_WEBHOOK_ENABLED", True)
    monkeypatch.setattr(settings, "RUMY_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(settings, "HANDOFF_TENANT_ID", str(tenant.id))
    # raise_server_exceptions=False: um 500 tem de aparecer como 500, não subir
    # como exceção — senão o teste "não vira 500" não consegue observar o 500.
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _h(body=BODY, ts=None, event_id=None, secret=SECRET):
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
    }


# ── ACHADO 16-H #1: Event ID não coberto pela assinatura ──────────────────────


class TestBindingEventId:
    def test_requisicao_assinada_nao_pode_ser_reaproveitada_trocando_o_event_id(
        self, client, session
    ):
        """O achado central da 16-H: 1 request → 3 linhas trocando só o header."""
        ts = str(int(time.time()))
        sig = expected_signature(ts, BODY, SECRET)
        for i in range(3):
            r = client.post(
                URL, content=BODY,
                headers={"X-Rumy-Signature": sig, "X-Rumy-Timestamp": ts,
                         "X-Rumy-Event-Id": f"evt_forjado_{i}"},
            )
            assert r.status_code == 400, "Event ID forjado tem de ser recusado"
        assert session.query(CrmLeadEvent).count() == 0, "nada pode ser persistido"

    def test_event_id_coerente_com_o_corpo_e_aceito(self, client):
        assert client.post(URL, content=BODY, headers=_h()).status_code == 200

    def test_corpo_sem_id_nao_exige_binding(self, client):
        """Produtor que não manda ``id`` no corpo: o header ainda governa."""
        body = json.dumps({"event_type": "lead.converted"}).encode()
        r = client.post(URL, content=body, headers=_h(body, event_id="evt_so_no_header"))
        assert r.status_code == 200


# ── ACHADO 16-H #2: Event ID maior que a coluna ───────────────────────────────


class TestEventIdDefensivo:
    def test_event_id_gigante_e_400_nao_500(self, client, session):
        r = client.post(URL, content=BODY, headers=_h(event_id="evt_" + "A" * 500))
        assert r.status_code == 400, f"esperado 400, veio {r.status_code}"
        assert session.query(CrmLeadEvent).count() == 0

    def test_limite_respeita_a_capacidade_da_coluna(self):
        """``idempotency_key`` é String(128) e a chave é ``evt:<id>``."""
        assert MAX_PROVIDER_EVENT_ID + len("evt:") <= 128
        assert is_valid_event_id("A" * MAX_PROVIDER_EVENT_ID)
        assert not is_valid_event_id("A" * (MAX_PROVIDER_EVENT_ID + 1))

    @pytest.mark.parametrize("hostil", ["evt_a\rb", "evt_a\nb", "evt_a\tb", "evt_a b", "", "   "])
    def test_controle_e_espaco_rejeitados(self, hostil):
        assert not is_valid_event_id(hostil)

    def test_event_id_ausente_e_400(self, client, session):
        h = _h()
        del h["X-Rumy-Event-Id"]
        assert client.post(URL, content=BODY, headers=h).status_code == 400
        assert session.query(CrmLeadEvent).count() == 0


# ── ACHADO 16-H #3: assinatura malformada ─────────────────────────────────────


class TestAssinaturaMalformada:
    @pytest.mark.parametrize(
        "sig",
        ["", "   ", "nao-e-base64!!", "a" * 5, "A" * 500, "abc$%&", "\x01\x02"],
    )
    def test_assinatura_malformada_e_401_nunca_500(self, client, sig):
        ts = str(int(time.time()))
        r = client.post(
            URL, content=BODY,
            headers={"X-Rumy-Signature": sig, "X-Rumy-Timestamp": ts,
                     "X-Rumy-Event-Id": EVENT_ID},
        )
        assert r.status_code == 401, f"sig={sig!r} deu {r.status_code}"

    def test_nao_ascii_no_nivel_da_funcao(self):
        """LIMITAÇÃO DOCUMENTADA: o TestClient recusa enviar header não-ASCII
        (UnicodeEncodeError no cliente), então o caminho HTTP real não é
        reproduzível aqui. O uvicorn decodifica headers em latin-1, o que
        produziria justamente um str não-ASCII. Testamos a função diretamente —
        é o mais próximo do servidor real que este harness alcança.
        """
        from app.services.handoff.webhook_auth import verify_signature

        ts = str(int(time.time()))
        # não levanta TypeError: o regex de base64 barra antes do compare_digest
        assert verify_signature(BODY, chr(255) * 44, ts) is False
        assert verify_signature(BODY, "ç" * 44, ts) is False


class TestTimestampDefensivo:
    @pytest.mark.parametrize(
        "ts", ["", "   ", "abc", "2026-08-28T13:00:00Z", "1_756_400_000",
               "-1756400000", "1e10", "99999999999999999999999"],
    )
    def test_carimbo_invalido_e_401_nunca_500(self, client, ts):
        r = client.post(
            URL, content=BODY,
            headers={"X-Rumy-Signature": expected_signature(ts, BODY, SECRET),
                     "X-Rumy-Timestamp": ts, "X-Rumy-Event-Id": EVENT_ID},
        )
        assert r.status_code == 401, f"ts={ts!r} deu {r.status_code}"

    def test_digitos_de_largura_total_no_nivel_da_funcao(self):
        """``int("１７５６")`` vale 1756 no Python — e não é o contrato.

        MESMA LIMITAÇÃO do teste de assinatura não-ASCII: o cliente HTTP recusa
        enviar o header (UnicodeEncodeError), então o caminho real não é
        reproduzível aqui. Verificamos a função diretamente.
        """
        from app.services.handoff.webhook_auth import _parse_timestamp

        assert _parse_timestamp("１７５６４００００") is None
        assert _parse_timestamp("1756400000") is not None


# ── ITEM 3: secret fail-closed ────────────────────────────────────────────────


class TestSecretFailClosed:
    @pytest.mark.parametrize("secret", [None, "", "   ", 12345, []])
    def test_secret_ausente_ou_invalido_rejeita_tudo(self, client, monkeypatch, secret):
        monkeypatch.setattr(settings, "RUMY_WEBHOOK_SECRET", secret)
        r = client.post(URL, content=BODY, headers=_h())
        assert r.status_code == 401, f"secret={secret!r} deu {r.status_code}"

    def test_hmac_nunca_calculado_com_chave_vazia(self, monkeypatch):
        """Assinatura derivada de chave vazia não pode autenticar nada."""
        from app.services.handoff import webhook_auth

        monkeypatch.setattr(settings, "RUMY_WEBHOOK_SECRET", "")
        ts = str(int(time.time()))
        assert webhook_auth.verify_signature(BODY, expected_signature(ts, BODY, ""), ts) is False


# ── ITEM 2: idempotência vinculada ao conteúdo ────────────────────────────────


class TestIntegridadeDoConteudo:
    def test_mesmo_id_mesmo_hash_e_retry_idempotente(self, client, session):
        client.post(URL, content=BODY, headers=_h())
        r = client.post(URL, content=BODY, headers=_h())
        assert r.status_code == 200 and r.json()["status"] == "duplicate"
        assert session.query(CrmLeadEvent).count() == 1

    def test_mesmo_id_hash_diferente_e_409_sem_substituir(self, client, session):
        b1 = json.dumps({"id": EVENT_ID, "v": 1}).encode()
        b2 = json.dumps({"id": EVENT_ID, "v": 2}).encode()
        client.post(URL, content=b1, headers=_h(b1))
        r = client.post(URL, content=b2, headers=_h(b2))
        assert r.status_code == 409, "divergência não pode ser descarte silencioso"
        row = session.query(CrmLeadEvent).one()
        assert str(row.payload_hash) == hashlib.sha256(b1).hexdigest()


# ── ITEM 6: teto de corpo ─────────────────────────────────────────────────────


class TestTetoDeCorpo:
    def test_corpo_acima_do_teto_e_413_sem_autenticar(self, client, session, monkeypatch):
        monkeypatch.setattr(settings, "RUMY_MAX_BODY_BYTES", 1024)
        grande = json.dumps({"id": EVENT_ID, "lixo": "x" * 5000}).encode()
        r = client.post(URL, content=grande, headers=_h(grande))
        assert r.status_code == 413
        assert session.query(CrmLeadEvent).count() == 0

    def test_teto_nao_confia_em_content_length(self, client, monkeypatch):
        """Content-Length mentiroso não deve liberar leitura ilimitada."""
        monkeypatch.setattr(settings, "RUMY_MAX_BODY_BYTES", 1024)
        grande = json.dumps({"id": EVENT_ID, "lixo": "x" * 5000}).encode()
        h = _h(grande)
        h["Content-Length"] = "10"  # mentira deliberada
        r = client.post(URL, content=grande, headers=h)
        assert r.status_code in (400, 413), f"veio {r.status_code}"

    def test_corpo_dentro_do_teto_passa(self, client):
        assert client.post(URL, content=BODY, headers=_h()).status_code == 200


# ── ITEM 5: higiene de logs ───────────────────────────────────────────────────


class TestHigieneDeLogs:
    def test_nao_registra_segredo_assinatura_nem_corpo(self, client, caplog):
        import logging

        caplog.set_level(logging.DEBUG)
        segredo_no_corpo = "CONTEUDO-SENSIVEL-NAO-DEVE-VAZAR"
        body = json.dumps({"id": EVENT_ID, "pii": segredo_no_corpo}).encode()
        ts = str(int(time.time()))
        assinatura = expected_signature(ts, body, SECRET)

        client.post(URL, content=body, headers=_h(body))                    # sucesso
        client.post(URL, content=body,                                       # falha
                    headers={"X-Rumy-Signature": "invalida", "X-Rumy-Timestamp": ts,
                             "X-Rumy-Event-Id": EVENT_ID})

        texto = caplog.text
        assert SECRET not in texto, "secret vazou no log"
        assert assinatura not in texto, "assinatura esperada vazou no log"
        assert segredo_no_corpo not in texto, "corpo íntegro vazou no log"


class TestFlagsPermanecemOff:
    def test_defaults(self):
        from app.config import Settings

        for flag in ("RUMY_WEBHOOK_ENABLED", "HANDOFF_APPLY_ENABLED"):
            assert Settings.model_fields[flag].default is False, flag
