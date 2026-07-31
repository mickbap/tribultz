"""Tests for AttioClient — PO-2026-07-CRM-001, fatia 1/12."""

from __future__ import annotations

import httpx
import pytest

from app.config import settings
from app.integrations.attio.client import AttioAPIError, AttioClient, is_enabled, noop, ping


@pytest.fixture(autouse=True)
def _attio_disabled_by_default(monkeypatch):
    """Guard: every test starts from the disabled state, mirroring HubSpot's guard."""
    monkeypatch.setattr(settings, "ATTIO_ENABLED", False)
    monkeypatch.setattr(settings, "ATTIO_API_KEY", "")


def _enable(monkeypatch, api_key: str = "test-key") -> None:
    monkeypatch.setattr(settings, "ATTIO_ENABLED", True)
    monkeypatch.setattr(settings, "ATTIO_API_KEY", api_key)


def _client(handler, **kwargs) -> AttioClient:
    return AttioClient(transport=httpx.MockTransport(handler), base_delay_seconds=0.001, **kwargs)


# ── Guard ─────────────────────────────────────────────────────
def test_is_enabled_false_without_key(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_ENABLED", True)
    monkeypatch.setattr(settings, "ATTIO_API_KEY", "")
    assert is_enabled() is False


def test_is_enabled_true_with_flag_and_key(monkeypatch):
    _enable(monkeypatch)
    assert is_enabled() is True


def test_noop_shape():
    result = noop("company")
    assert result == {"attio": "disabled", "entity": "company", "action": "skipped"}


def test_ping_is_noop_when_disabled():
    assert ping() == {"attio": "disabled", "entity": "ping", "action": "skipped"}


# ── Happy path ────────────────────────────────────────────────
def test_request_success_returns_json(monkeypatch):
    _enable(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"data": []})

    client = _client(handler)
    result = client.request("GET", "/objects")
    assert result == {"data": []}


def test_request_success_empty_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = _client(handler)
    assert client.request("DELETE", "/objects/companies/records/123") == {}


# ── Retry policy ──────────────────────────────────────────────
def test_get_retries_on_429_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"message": "rate limited"})
        return httpx.Response(200, json={"ok": True})

    client = _client(handler)
    result = client.request("GET", "/objects")
    assert result == {"ok": True}
    assert calls["n"] == 3


def test_get_retries_on_500_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503, json={"message": "unavailable"})
        return httpx.Response(200, json={"ok": True})

    client = _client(handler)
    result = client.request("PUT", "/objects/companies/records")
    assert result == {"ok": True}
    assert calls["n"] == 2


def test_post_does_not_retry_on_500():
    """A POST that returns 5xx must not be retried — it may have already
    created the record server-side, and retrying risks a duplicate."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"message": "boom"})

    client = _client(handler)
    with pytest.raises(AttioAPIError) as exc_info:
        client.request("POST", "/objects/companies/records")
    assert calls["n"] == 1
    assert exc_info.value.status_code == 500


def test_post_retries_on_429():
    """A POST rejected with 429 was never processed server-side — safe to retry."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(429, json={"message": "rate limited"})
        return httpx.Response(201, json={"id": "abc"})

    client = _client(handler)
    result = client.request("POST", "/objects/companies/records")
    assert result == {"id": "abc"}
    assert calls["n"] == 2


def test_retries_exhausted_raises():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={"message": "still down"})

    client = _client(handler, max_retries=2)
    with pytest.raises(AttioAPIError) as exc_info:
        client.request("GET", "/objects")
    assert exc_info.value.status_code == 503
    assert calls["n"] == 3  # initial attempt + 2 retries


def test_non_retryable_4xx_raises_immediately():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, json={"message": "not found"})

    client = _client(handler)
    with pytest.raises(AttioAPIError) as exc_info:
        client.request("GET", "/objects/companies/records/missing")
    assert exc_info.value.status_code == 404
    assert calls["n"] == 1


def test_respects_retry_after_header():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"message": "slow down"})
        return httpx.Response(200, json={"ok": True})

    client = _client(handler)
    assert client.request("GET", "/objects") == {"ok": True}


def test_transport_error_retries_then_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _client(handler, max_retries=1)
    with pytest.raises(AttioAPIError):
        client.request("GET", "/objects")
