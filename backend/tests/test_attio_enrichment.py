"""Tests for the Attio enrichment sync — PO-2026-07-CRM-001, fatia 5/12."""

from __future__ import annotations

import json as _json

import httpx
import pytest

from app.config import settings
from app.integrations.attio.client import AttioClient
from app.integrations.attio.enrichment import sync_enrichment


@pytest.fixture(autouse=True)
def _attio_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_ENABLED", True)
    monkeypatch.setattr(settings, "ATTIO_API_KEY", "test-key")


def _client(handler) -> AttioClient:
    return AttioClient(transport=httpx.MockTransport(handler), base_delay_seconds=0.001)


def test_syncs_all_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/v2/objects/companies/records/company-1"
        values = _json.loads(request.read())["data"]["values"]
        assert values == {
            "score_tribultz": 87.5,
            "ranking": 12,
            "score_reason": "Alto potencial de conversão — segmento contábil",
            "analysis_date": "2026-07-31",
            "last_updated_date": "2026-07-31",
            "rf_origin": "Receita Federal — Dados Abertos CNPJ 2026-07",
            "financial_indicators": '{"faturamento_estimado": 500000}',
            "segment": "Contabilidade",
            "cnae": "6920-6/01",
        }
        return httpx.Response(200, json={"data": {"id": {"record_id": "company-1"}}})

    result = sync_enrichment(
        "company-1",
        score=87.5,
        ranking=12,
        score_reason="Alto potencial de conversão — segmento contábil",
        analysis_date="2026-07-31",
        last_updated_date="2026-07-31",
        rf_origin="Receita Federal — Dados Abertos CNPJ 2026-07",
        financial_indicators={"faturamento_estimado": 500000},
        segment="Contabilidade",
        cnae="6920-6/01",
        client=_client(handler),
    )
    assert result == {"data": {"id": {"record_id": "company-1"}}}


def test_syncs_partial_subset_and_omits_none_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        values = _json.loads(request.read())["data"]["values"]
        assert values == {"score_tribultz": 42.0, "ranking": 5}
        return httpx.Response(200, json={"data": {}})

    sync_enrichment("company-1", score=42.0, ranking=5, client=_client(handler))


def test_preserves_falsy_but_meaningful_values():
    def handler(request: httpx.Request) -> httpx.Response:
        values = _json.loads(request.read())["data"]["values"]
        assert values == {"score_tribultz": 0, "financial_indicators": "{}"}
        return httpx.Response(200, json={"data": {}})

    sync_enrichment("company-1", score=0, financial_indicators={}, client=_client(handler))


def test_raises_without_calling_api_when_nothing_passed():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("API não deveria ser chamada sem nenhum campo")

    with pytest.raises(ValueError, match="nenhum campo informado"):
        sync_enrichment("company-1", client=_client(handler))


def test_disabled_returns_noop(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_ENABLED", False)
    result = sync_enrichment("company-1", score=10)
    assert result == {"attio": "disabled", "entity": "enrichment", "action": "skipped"}


def test_uses_custom_object_type():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/objects/people/records/person-1"
        return httpx.Response(200, json={"data": {}})

    sync_enrichment("person-1", score=10, object_type="people", client=_client(handler))
