"""Ordem 04: infraestrutura do piloto CBS v2, com fixtures só sintéticas."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.config import Settings, settings
from app.database import get_db
from app.main import app
from app.models.auth import Tenant
from app.models.cbs_v2_pilot import (
    CbsV2ExternalObservation,
    CbsV2SyncRun,
    CbsV2SyncRunEvent,
)
from app.services.cbs_v2_pilot import (
    CONTRACT_VERSION,
    PilotDisabledError,
    get_sync_run_for_tenant,
    ingest_external_payload,
    parse_external_payload,
    pilot_activation_gates,
    pilot_is_active,
    prepare_sync_run,
    recover_ticket_status,
)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz"
)
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
FIXTURE = Path(__file__).parent / "fixtures/cbs_v2/SYNTHETIC_NON_OFFICIAL_status_with_unknown.json"


@pytest.fixture(name="session")
def session_fixture():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(name="tenants")
def tenants_fixture(session):
    tenant_a = Tenant(name="CBS V2 Tenant A", slug=f"cbs-v2-a-{uuid.uuid4()}")
    tenant_b = Tenant(name="CBS V2 Tenant B", slug=f"cbs-v2-b-{uuid.uuid4()}")
    session.add_all([tenant_a, tenant_b])
    session.flush()
    return tenant_a, tenant_b


@pytest.fixture(name="active_pilot")
def active_pilot_fixture(monkeypatch):
    monkeypatch.setattr(settings, "CBS_V2_PILOT_ENABLED", True)
    monkeypatch.setattr(settings, "CBS_V2_API_AVAILABLE", True)
    monkeypatch.setattr(settings, "CBS_V2_REAL_PAYLOAD_OBSERVED", True)
    monkeypatch.setattr(settings, "CBS_V2_CLIENT_ID", "client-sintetico")
    monkeypatch.setattr(settings, "CBS_V2_CLIENT_SECRET", "secret-sintetico")
    monkeypatch.setattr(settings, "CBS_V2_API_BASE_URL", "https://example.invalid")


@pytest.fixture(name="stored_raw")
def stored_raw_fixture(monkeypatch):
    calls = []

    def fake_put(*, key, data, content_type, metadata):
        calls.append({"key": key, "data": data, "content_type": content_type, "metadata": metadata})
        return {
            "bucket": "synthetic-test-bucket",
            "key": key,
            "checksum_sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
        }

    monkeypatch.setattr("app.services.cbs_v2_pilot.put_immutable_object", fake_put)
    return calls


def _prepared(session, tenant_id):
    return prepare_sync_run(
        session,
        tenant_id=tenant_id,
        environment="PRODUCAO_RESTRITA",
        resource="CREDITOS",
        cnpj_base="12345678",
        callback_base_url="https://api.tribultz.invalid/api/v1/webhooks/cbs-v2",
        requested_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )


class TestActivation:
    def test_defaults_estao_todos_fechados(self):
        assert Settings.model_fields["CBS_V2_PILOT_ENABLED"].default is False
        assert Settings.model_fields["CBS_V2_API_AVAILABLE"].default is False
        assert Settings.model_fields["CBS_V2_REAL_PAYLOAD_OBSERVED"].default is False

    def test_quatro_gates_sao_cumulativos(self, active_pilot, monkeypatch):
        assert pilot_is_active() is True
        for setting_name in (
            "CBS_V2_PILOT_ENABLED",
            "CBS_V2_API_AVAILABLE",
            "CBS_V2_REAL_PAYLOAD_OBSERVED",
        ):
            monkeypatch.setattr(settings, setting_name, False)
            assert pilot_is_active() is False
            monkeypatch.setattr(settings, setting_name, True)
        monkeypatch.setattr(settings, "CBS_V2_CLIENT_SECRET", "")
        assert pilot_is_active() is False
        assert pilot_activation_gates()["CREDENCIAL_PILOTO"] is False


class TestParserFailClosed:
    def test_desconhecido_preservado_sem_vazar_url_assinada(self):
        raw = FIXTURE.read_bytes()
        parsed = parse_external_payload(raw)
        assert parsed.schema_status == "UNKNOWN_FIELDS"
        assert "campoFuturoDesconhecido" in parsed.unknown_fields
        assert parsed.sanitized_payload["campoFuturoDesconhecido"] == {"preservar": True}
        assert parsed.sanitized_payload["urlAssinada"] == "[REDACTED_URL]"
        assert "SEGREDO-SINTETICO" not in json.dumps(parsed.sanitized_payload)

    @pytest.mark.parametrize(
        ("raw", "status"),
        [(b"nao-json", "NON_JSON"), (b"[]", "INCOMPATIBLE")],
    )
    def test_incompativel_permanece_indeterminado(self, raw, status):
        parsed = parse_external_payload(raw)
        assert parsed.schema_status == status
        assert parsed.state == "INDETERMINADO"
        assert parsed.ticket is None


class TestLedgerAndIsolation:
    def test_linhagem_fingerprints_raw_e_idempotencia_ticket_fingerprint(
        self, session, tenants, stored_raw
    ):
        tenant_a, _ = tenants
        prepared = _prepared(session, tenant_a.id)
        assert prepared.run.contract_version == CONTRACT_VERSION
        assert prepared.run.request_fingerprint == hashlib.sha256(prepared.request_body).hexdigest()
        assert str(prepared.run.callback_id) in prepared.callback_url

        raw = FIXTURE.read_bytes()
        first = ingest_external_payload(
            session,
            run=prepared.run,
            raw_body=raw,
            source="WEBHOOK",
            synthetic_fixture=True,
        )
        second = ingest_external_payload(
            session,
            run=prepared.run,
            raw_body=raw,
            source="STATUS_POLL",
            synthetic_fixture=True,
        )

        assert first.created is True
        assert second.created is False
        assert second.event.id == first.event.id
        assert session.query(CbsV2SyncRunEvent).count() == 1
        assert session.query(CbsV2ExternalObservation).count() == 1
        assert len(stored_raw) == 1
        assert stored_raw[0]["data"] == raw
        assert first.event.response_fingerprint == hashlib.sha256(raw).hexdigest()
        assert first.event.artifact_fingerprint == first.event.response_fingerprint
        assert first.event.result == "INDETERMINADO"
        assert first.observation.comparability == "NOT_COMPARABLE"
        assert first.observation.determination == "INDETERMINADO"
        assert first.observation.external_transaction_id is None
        assert first.observation.previous_observation_id is None
        assert first.observation.observation_version == 1
        assert first.observation.synthetic_fixture is True

    def test_arquivo_bruto_nao_json_e_preservado_sem_identidade_inferida(
        self, session, tenants, stored_raw
    ):
        tenant_a, _ = tenants
        run = _prepared(session, tenant_a.id).run
        raw_file = b"ARQUIVO SINTETICO NAO OFICIAL\nSEM SCHEMA OBSERVADO\n"
        ingested = ingest_external_payload(
            session,
            run=run,
            raw_body=raw_file,
            source="DOWNLOAD_ARTIFACT",
            content_type="application/octet-stream",
            synthetic_fixture=True,
            ticket_hint="ticket-sintetico-download",
        )
        assert ingested.event.ticket == "ticket-sintetico-download"
        assert ingested.event.result == "INDETERMINADO"
        assert ingested.observation.schema_status == "NON_JSON"
        assert ingested.observation.external_transaction_id is None
        assert stored_raw[0]["data"] == raw_file

    def test_consulta_e_estritamente_tenant_scoped(self, session, tenants):
        tenant_a, tenant_b = tenants
        run = _prepared(session, tenant_a.id).run
        assert get_sync_run_for_tenant(session, tenant_id=tenant_a.id, sync_run_id=run.id)
        assert get_sync_run_for_tenant(session, tenant_id=tenant_b.id, sync_run_id=run.id) is None

    def test_banco_recusa_update_do_ledger(self, session, tenants):
        tenant_a, _ = tenants
        run = _prepared(session, tenant_a.id).run
        savepoint = session.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(
                update(CbsV2SyncRun)
                .where(CbsV2SyncRun.id == run.id)
                .values(resource="DEBITOS")
            )
            session.flush()
        savepoint.rollback()
        session.expire(run)
        assert run.resource == "CREDITOS"


class TestWebhook:
    def test_desligado_parece_inexistente(self, session, tenants):
        run = _prepared(session, tenants[0].id).run

        def override_db():
            yield session

        app.dependency_overrides[get_db] = override_db
        try:
            response = TestClient(app).post(
                f"/api/v1/webhooks/cbs-v2/{run.callback_id}", content=b"{}"
            )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_callback_resolve_tenant_e_nao_vaza_url(
        self, session, tenants, stored_raw, active_pilot, monkeypatch, caplog
    ):
        run = _prepared(session, tenants[0].id).run

        def override_db():
            yield session

        app.dependency_overrides[get_db] = override_db
        monkeypatch.setattr(session, "commit", session.flush)
        caplog.set_level(logging.DEBUG)
        raw = FIXTURE.read_bytes()
        try:
            response = TestClient(app).post(
                f"/api/v1/webhooks/cbs-v2/{run.callback_id}",
                content=raw,
                headers={"content-type": "application/json"},
            )
            assert response.status_code == 202
            assert response.json() == {
                "status": "accepted",
                "state": "CONCLUIDA",
                "result": "INDETERMINADO",
            }
            observation = session.scalar(select(CbsV2ExternalObservation))
            assert observation.tenant_id == tenants[0].id
            assert "SEGREDO-SINTETICO" not in caplog.text
            assert "SEGREDO-SINTETICO" not in json.dumps(observation.sanitized_payload)
        finally:
            app.dependency_overrides.clear()

    def test_storage_failure_nao_cria_estado(self, session, tenants, active_pilot, monkeypatch):
        run = _prepared(session, tenants[0].id).run

        def override_db():
            yield session

        def fail_storage(**kwargs):  # noqa: ARG001
            raise RuntimeError("storage unavailable")

        app.dependency_overrides[get_db] = override_db
        monkeypatch.setattr("app.services.cbs_v2_pilot.put_immutable_object", fail_storage)
        monkeypatch.setattr(session, "rollback", session.expire_all)
        try:
            response = TestClient(app, raise_server_exceptions=False).post(
                f"/api/v1/webhooks/cbs-v2/{run.callback_id}", content=FIXTURE.read_bytes()
            )
            assert response.status_code == 503
            assert session.query(CbsV2SyncRunEvent).count() == 0
            assert session.query(CbsV2ExternalObservation).count() == 0
        finally:
            app.dependency_overrides.clear()


class TestStatusRecovery:
    def test_status_poll_tenant_scoped_e_append_only(
        self, session, tenants, stored_raw, active_pilot
    ):
        tenant_a, tenant_b = tenants
        run = _prepared(session, tenant_a.id).run
        accepted = json.dumps({"tiqueteSolicitacao": "ticket-sintetico-status"}).encode()
        ingest_external_payload(
            session, run=run, raw_body=accepted, source="REQUEST_RESPONSE", synthetic_fixture=True
        )

        with pytest.raises(Exception):
            recover_ticket_status(
                session,
                tenant_id=tenant_b.id,
                sync_run_id=run.id,
                access_token="token-sintetico",
            )

        requested_urls = []

        def handler(request: httpx.Request):
            requested_urls.append(str(request.url))
            assert request.headers["authorization"] == "Bearer token-sintetico"
            return httpx.Response(
                200,
                json={
                    "tiqueteSolicitacao": "ticket-sintetico-status",
                    "situacao": "EM_PROCESSAMENTO",
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        result = recover_ticket_status(
            session,
            tenant_id=tenant_a.id,
            sync_run_id=run.id,
            access_token="token-sintetico",
            client=client,
        )
        client.close()
        assert result.event.source == "STATUS_POLL"
        assert result.event.state == "EM_PROCESSAMENTO"
        assert result.event.transport_status_code == 200
        assert result.event.previous_event_id is not None
        assert requested_urls == [
            "https://example.invalid/apuracao-cbs-prr/v2/situacao/ticket-sintetico-status"
        ]

    def test_status_poll_bloqueado_sem_quatro_gates(self, session, tenants):
        run = _prepared(session, tenants[0].id).run
        with pytest.raises(PilotDisabledError):
            recover_ticket_status(
                session,
                tenant_id=tenants[0].id,
                sync_run_id=run.id,
                access_token="token-sintetico",
            )
