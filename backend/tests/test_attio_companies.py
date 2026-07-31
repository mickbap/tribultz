"""Tests for the Attio company sync — PO-2026-07-CRM-001, fatia 2/12."""

from __future__ import annotations

import httpx
import pytest

from app.config import settings
from app.integrations.attio.client import AttioClient
from app.integrations.attio.companies import upsert_company


@pytest.fixture(autouse=True)
def _attio_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_ENABLED", True)
    monkeypatch.setattr(settings, "ATTIO_API_KEY", "test-key")


def _client(handler) -> AttioClient:
    return AttioClient(transport=httpx.MockTransport(handler), base_delay_seconds=0.001)


def test_disabled_returns_noop(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_ENABLED", False)
    result = upsert_company(name="Contabilidade Exemplo")
    assert result == {"attio": "disabled", "entity": "company", "action": "skipped"}


def test_creates_when_nothing_found():
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/records/query"):
            return httpx.Response(200, json={"records": []})
        assert request.method == "PUT"
        assert request.url.params["matching_attribute"] == "cnpj"
        body = request.read()
        import json as _json

        payload = _json.loads(body)
        assert payload["data"]["values"]["cnpj"] == "12345678000199"
        return httpx.Response(200, json={"data": {"id": {"record_id": "new-1"}}})

    result = upsert_company(
        name="Contabilidade Exemplo",
        cnpj="12345678000199",
        domain="exemplo.com.br",
        client=_client(handler),
    )
    assert result == {"data": {"id": {"record_id": "new-1"}}}
    # Searched by CNPJ then domain before creating.
    assert calls == [
        ("POST", "/v2/objects/companies/records/query"),
        ("POST", "/v2/objects/companies/records/query"),
        ("PUT", "/v2/objects/companies/records"),
    ]


def test_updates_when_found_by_cnpj():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/records/query"):
            return httpx.Response(
                200, json={"records": [{"id": {"record_id": "existing-1"}}]}
            )
        assert request.method == "PATCH"
        assert request.url.path == "/v2/objects/companies/records/existing-1"
        return httpx.Response(200, json={"data": {"id": {"record_id": "existing-1"}}})

    result = upsert_company(
        name="Contabilidade Exemplo",
        cnpj="12345678000199",
        client=_client(handler),
    )
    assert result == {"data": {"id": {"record_id": "existing-1"}}}


def test_updates_when_found_by_domain_after_cnpj_miss():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/records/query"):
            import json as _json

            filter_attr = next(iter(_json.loads(request.read())["filter"]))
            calls.append(filter_attr)
            if filter_attr == "cnpj":
                return httpx.Response(200, json={"records": []})
            return httpx.Response(
                200, json={"records": [{"id": {"record_id": "existing-2"}}]}
            )
        assert request.method == "PATCH"
        assert request.url.path == "/v2/objects/companies/records/existing-2"
        return httpx.Response(200, json={"data": {"id": {"record_id": "existing-2"}}})

    result = upsert_company(
        name="Contabilidade Exemplo",
        cnpj="00000000000000",
        domain="exemplo.com.br",
        client=_client(handler),
    )
    assert result == {"data": {"id": {"record_id": "existing-2"}}}
    assert calls == ["cnpj", "domains"]


def test_uses_attio_company_id_directly_without_search():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/v2/objects/companies/records/known-id"
        return httpx.Response(200, json={"data": {"id": {"record_id": "known-id"}}})

    result = upsert_company(
        name="Contabilidade Exemplo",
        cnpj="12345678000199",
        attio_company_id="known-id",
        client=_client(handler),
    )
    assert result == {"data": {"id": {"record_id": "known-id"}}}


def test_create_matching_attribute_falls_back_to_domain_without_cnpj():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/records/query"):
            return httpx.Response(200, json={"records": []})
        assert request.url.params["matching_attribute"] == "domains"
        return httpx.Response(200, json={"data": {"id": {"record_id": "new-2"}}})

    result = upsert_company(
        name="Contabilidade Exemplo",
        domain="exemplo.com.br",
        client=_client(handler),
    )
    assert result == {"data": {"id": {"record_id": "new-2"}}}


def test_create_matching_attribute_falls_back_to_name_without_cnpj_or_domain():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["matching_attribute"] == "name"
        return httpx.Response(200, json={"data": {"id": {"record_id": "new-3"}}})

    result = upsert_company(name="Contabilidade Exemplo", client=_client(handler))
    assert result == {"data": {"id": {"record_id": "new-3"}}}
