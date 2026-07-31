"""Tests for the Attio history logging — PO-2026-07-CRM-001, fatia 6/12."""

from __future__ import annotations

import json as _json

import httpx
import pytest

from app.config import settings
from app.integrations.attio.client import AttioClient
from app.integrations.attio.history import log_history


@pytest.fixture(autouse=True)
def _attio_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_ENABLED", True)
    monkeypatch.setattr(settings, "ATTIO_API_KEY", "test-key")


def _client(handler) -> AttioClient:
    return AttioClient(transport=httpx.MockTransport(handler), base_delay_seconds=0.001)


@pytest.mark.parametrize(
    "event_type,expected_title",
    [
        ("criacao", "Lead criado"),
        ("atualizacao", "Lead atualizado"),
        ("mudanca_estagio", "Estágio alterado"),
        ("campanha_enviada", "Campanha enviada"),
        ("resposta_recebida", "Resposta recebida"),
        ("observacao", "Observação automática"),
    ],
)
def test_creates_note_for_each_valid_event_type(event_type, expected_title):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v2/notes"
        payload = _json.loads(request.read())["data"]
        assert payload == {
            "parent_object": "companies",
            "parent_record_id": "company-1",
            "title": expected_title,
            "format": "plaintext",
            "content": "detalhe do evento",
        }
        return httpx.Response(200, json={"data": {"id": {"note_id": "note-1"}}})

    result = log_history(
        "company-1", event_type, "detalhe do evento", client=_client(handler)
    )
    assert result == {"data": {"id": {"note_id": "note-1"}}}


def test_rejects_invalid_event_type_without_calling_api():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("API não deveria ser chamada com event_type inválido")

    with pytest.raises(ValueError, match="tipo de evento de histórico inválido"):
        log_history("company-1", "evento_desconhecido", "x", client=_client(handler))


def test_disabled_returns_noop(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_ENABLED", False)
    result = log_history("company-1", "criacao", "novo lead")
    assert result == {"attio": "disabled", "entity": "history_note", "action": "skipped"}


def test_uses_custom_parent_object():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = _json.loads(request.read())["data"]
        assert payload["parent_object"] == "people"
        assert payload["parent_record_id"] == "person-1"
        return httpx.Response(200, json={"data": {}})

    log_history(
        "person-1",
        "resposta_recebida",
        "respondeu o e-mail",
        parent_object="people",
        client=_client(handler),
    )


def test_repeated_call_creates_a_new_note_each_time():
    """History has no dedup by design — two calls are two notes."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"data": {"id": {"note_id": f"note-{calls['n']}"}}})

    client = _client(handler)
    first = log_history("company-1", "atualizacao", "primeira", client=client)
    second = log_history("company-1", "atualizacao", "segunda", client=client)
    assert first != second
    assert calls["n"] == 2
