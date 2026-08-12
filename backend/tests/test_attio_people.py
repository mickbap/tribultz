"""Tests for the Attio person sync — PO-2026-07-CRM-001, fatia 3/12."""

from __future__ import annotations

import json as _json

import httpx
import pytest

from app.config import settings
from app.integrations.attio.client import AttioClient
from app.integrations.attio.people import upsert_person


@pytest.fixture(autouse=True)
def _attio_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_ENABLED", True)
    monkeypatch.setattr(settings, "ATTIO_API_KEY", "test-key")


def _client(handler) -> AttioClient:
    return AttioClient(transport=httpx.MockTransport(handler), base_delay_seconds=0.001)


def test_disabled_returns_noop(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_ENABLED", False)
    result = upsert_person(email="ana@exemplo.com.br")
    assert result == {"attio": "disabled", "entity": "person", "action": "skipped"}


def test_creates_when_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/records/query"):
            return httpx.Response(200, json={"records": []})
        assert request.method == "PUT"
        assert request.url.params["matching_attribute"] == "email_addresses"
        payload = _json.loads(request.read())
        values = payload["data"]["values"]
        assert values["email_addresses"] == ["ana@exemplo.com.br"]
        assert values["name"] == {"first_name": "Ana", "last_name": "Silva"}
        return httpx.Response(200, json={"data": {"id": {"record_id": "person-1"}}})

    result = upsert_person(
        email="ana@exemplo.com.br",
        first_name="Ana",
        last_name="Silva",
        client=_client(handler),
    )
    assert result == {"data": {"id": {"record_id": "person-1"}}}


def test_updates_when_found_by_email():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/records/query"):
            payload = _json.loads(request.read())
            assert payload["filter"] == {"email_addresses": {"$eq": "ana@exemplo.com.br"}}
            return httpx.Response(200, json={"records": [{"id": {"record_id": "person-2"}}]})
        assert request.method == "PATCH"
        assert request.url.path == "/v2/objects/people/records/person-2"
        return httpx.Response(200, json={"data": {"id": {"record_id": "person-2"}}})

    result = upsert_person(email="ana@exemplo.com.br", client=_client(handler))
    assert result == {"data": {"id": {"record_id": "person-2"}}}


def test_uses_attio_person_id_directly_without_search():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/v2/objects/people/records/known-id"
        return httpx.Response(200, json={"data": {"id": {"record_id": "known-id"}}})

    result = upsert_person(
        email="ana@exemplo.com.br",
        attio_person_id="known-id",
        client=_client(handler),
    )
    assert result == {"data": {"id": {"record_id": "known-id"}}}


def test_links_company_by_domain_shorthand():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/records/query"):
            return httpx.Response(200, json={"records": []})
        payload = _json.loads(request.read())
        assert payload["data"]["values"]["company"] == ["exemplo.com.br"]
        return httpx.Response(200, json={"data": {"id": {"record_id": "person-3"}}})

    result = upsert_person(
        email="ana@exemplo.com.br",
        company_domain="exemplo.com.br",
        client=_client(handler),
    )
    assert result == {"data": {"id": {"record_id": "person-3"}}}


def test_optional_fields_included_when_present():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/records/query"):
            return httpx.Response(200, json={"records": []})
        payload = _json.loads(request.read())
        values = payload["data"]["values"]
        assert values["job_title"] == "Diretora Financeira"
        assert values["linkedin"] == "https://linkedin.com/in/ana-silva"
        assert values["phone_numbers"] == "+5511999999999"
        return httpx.Response(200, json={"data": {"id": {"record_id": "person-4"}}})

    result = upsert_person(
        email="ana@exemplo.com.br",
        job_title="Diretora Financeira",
        linkedin="https://linkedin.com/in/ana-silva",
        phone="+5511999999999",
        client=_client(handler),
    )
    assert result == {"data": {"id": {"record_id": "person-4"}}}


def test_optional_fields_omitted_when_absent():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/records/query"):
            return httpx.Response(200, json={"records": []})
        payload = _json.loads(request.read())
        values = payload["data"]["values"]
        assert "job_title" not in values
        assert "linkedin" not in values
        assert "phone_numbers" not in values
        assert "name" not in values
        assert "company" not in values
        return httpx.Response(200, json={"data": {"id": {"record_id": "person-5"}}})

    result = upsert_person(email="ana@exemplo.com.br", client=_client(handler))
    assert result == {"data": {"id": {"record_id": "person-5"}}}


def test_links_company_by_record_id_sem_dominio():
    """Round 6 §2: vínculo por record_id — funciona p/ empresa SEM domínio e
    tem precedência sobre o shorthand de domínio."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/records/query"):
            return httpx.Response(200, json={"records": []})
        payload = _json.loads(request.read())
        assert payload["data"]["values"]["company"] == [
            {"target_object": "companies", "target_record_id": "company-sem-dominio-1"}
        ]
        return httpx.Response(200, json={"data": {"id": {"record_id": "person-9"}}})

    result = upsert_person(
        email="sintetica.qa@example.test",
        company_domain="ignorado.example",  # record_id vence
        company_record_id="company-sem-dominio-1",
        client=_client(handler),
    )
    assert result == {"data": {"id": {"record_id": "person-9"}}}
