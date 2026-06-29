"""Tests for GA4 Measurement Protocol service (server-side purchase event)."""
from __future__ import annotations

from app.services import ga4_mp


class _FakeResponse:
    def __init__(self, status_code: int = 204, text: str = ""):
        self.status_code = status_code
        self.text = text


def test_noop_without_api_secret(monkeypatch):
    """Sem GA4_MP_API_SECRET, não envia nada e retorna False."""
    monkeypatch.setattr(ga4_mp.settings, "GA4_MP_API_SECRET", "", raising=False)
    called = False

    def _fake_post(*args, **kwargs):  # pragma: no cover - não deve ser chamado
        nonlocal called
        called = True
        return _FakeResponse()

    monkeypatch.setattr(ga4_mp.httpx, "post", _fake_post)
    sent = ga4_mp.send_purchase(client_id="u1", transaction_id="pay_1", value=149.0, plan="Profissional")
    assert sent is False
    assert called is False


def test_sends_purchase_with_correct_payload(monkeypatch):
    monkeypatch.setattr(ga4_mp.settings, "GA4_MP_API_SECRET", "secret-123", raising=False)
    monkeypatch.setattr(ga4_mp.settings, "GA4_MEASUREMENT_ID", "G-TEST", raising=False)
    captured: dict = {}

    def _fake_post(url, params=None, json=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["json"] = json
        return _FakeResponse(status_code=204)

    monkeypatch.setattr(ga4_mp.httpx, "post", _fake_post)
    sent = ga4_mp.send_purchase(
        client_id="user-9", transaction_id="pay_42", value=149.0, plan="Profissional", user_id="user-9"
    )

    assert sent is True
    assert captured["params"] == {"measurement_id": "G-TEST", "api_secret": "secret-123"}
    body = captured["json"]
    assert body["client_id"] == "user-9"
    assert body["user_id"] == "user-9"
    event = body["events"][0]
    assert event["name"] == "purchase"
    assert event["params"]["transaction_id"] == "pay_42"
    assert event["params"]["value"] == 149.0
    assert event["params"]["currency"] == "BRL"
    assert event["params"]["items"][0]["item_name"] == "Profissional"


def test_never_raises_on_network_error(monkeypatch):
    monkeypatch.setattr(ga4_mp.settings, "GA4_MP_API_SECRET", "secret-123", raising=False)

    def _boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(ga4_mp.httpx, "post", _boom)
    # Não deve levantar — telemetria nunca quebra o webhook de pagamento.
    assert ga4_mp.send_purchase(client_id="u", transaction_id="t", value=1.0, plan="X") is False


def test_non_2xx_returns_false(monkeypatch):
    monkeypatch.setattr(ga4_mp.settings, "GA4_MP_API_SECRET", "secret-123", raising=False)
    monkeypatch.setattr(ga4_mp.httpx, "post", lambda *a, **k: _FakeResponse(status_code=400, text="bad"))
    assert ga4_mp.send_purchase(client_id="u", transaction_id="t", value=1.0, plan="X") is False
