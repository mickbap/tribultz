"""Tests for the Attio pipeline sync — PO-2026-07-CRM-001, fatia 4/12."""

from __future__ import annotations

import json as _json

import httpx
import pytest

from app.config import settings
from app.integrations.attio.client import AttioClient
from app.integrations.attio.pipeline import add_to_pipeline, set_lead_source


@pytest.fixture(autouse=True)
def _attio_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_ENABLED", True)
    monkeypatch.setattr(settings, "ATTIO_API_KEY", "test-key")
    monkeypatch.setattr(settings, "ATTIO_DEFAULT_PIPELINE", "pipeline-comercial")
    monkeypatch.setattr(settings, "ATTIO_DEFAULT_STAGE", "Lead identificado")


def _client(handler) -> AttioClient:
    return AttioClient(transport=httpx.MockTransport(handler), base_delay_seconds=0.001)


# ── add_to_pipeline ──────────────────────────────────────────
def test_moves_to_given_stage():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == "/v2/lists/pipeline-comercial/entries"
        payload = _json.loads(request.read())
        assert payload["data"]["parent_record_id"] == "company-1"
        assert payload["data"]["parent_object"] == "companies"
        assert payload["data"]["entry_values"] == {"stage": "Discovery"}
        return httpx.Response(200, json={"data": {"id": {"entry_id": "entry-1"}}})

    result = add_to_pipeline(
        "company-1", "companies", stage="Discovery", client=_client(handler)
    )
    assert result == {"data": {"id": {"entry_id": "entry-1"}}}


def test_defaults_to_configured_stage_and_pipeline():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/lists/pipeline-comercial/entries"
        payload = _json.loads(request.read())
        assert payload["data"]["entry_values"] == {"stage": "Lead identificado"}
        return httpx.Response(200, json={"data": {}})

    add_to_pipeline("company-1", "companies", client=_client(handler))


def test_rejects_invalid_stage_without_calling_api():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("API não deveria ser chamada com estágio inválido")

    with pytest.raises(ValueError, match="estágio inválido"):
        add_to_pipeline(
            "company-1", "companies", stage="Estágio Inexistente", client=_client(handler)
        )


def test_disabled_returns_noop(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_ENABLED", False)
    result = add_to_pipeline("company-1", "companies", stage="Discovery")
    assert result == {"attio": "disabled", "entity": "pipeline_entry", "action": "skipped"}


def test_uses_custom_list_slug():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/lists/outra-lista/entries"
        return httpx.Response(200, json={"data": {}})

    add_to_pipeline(
        "company-1",
        "companies",
        stage="Discovery",
        list_slug="outra-lista",
        client=_client(handler),
    )


# ── set_lead_source ───────────────────────────────────────────
def test_sets_valid_lead_source():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/v2/objects/companies/records/company-1"
        payload = _json.loads(request.read())
        assert payload["data"]["values"] == {"lead_source": "LinkedIn"}
        return httpx.Response(200, json={"data": {"id": {"record_id": "company-1"}}})

    result = set_lead_source("company-1", "LinkedIn", client=_client(handler))
    assert result == {"data": {"id": {"record_id": "company-1"}}}


def test_rejects_invalid_lead_source_without_calling_api():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("API não deveria ser chamada com lead source inválido")

    with pytest.raises(ValueError, match="lead source inválido"):
        set_lead_source("company-1", "Anúncio pago", client=_client(handler))


def test_lead_source_disabled_returns_noop(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_ENABLED", False)
    result = set_lead_source("company-1", "Manual")
    assert result == {"attio": "disabled", "entity": "lead_source", "action": "skipped"}


def test_lead_source_uses_custom_object_type():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/objects/people/records/person-1"
        return httpx.Response(200, json={"data": {}})

    set_lead_source("person-1", "Indicação", object_type="people", client=_client(handler))
