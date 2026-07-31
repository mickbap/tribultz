"""Tests for the Attio webhook signature verification and router —
PO-2026-07-CRM-001, fatia 7/12."""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.config import settings
from app.integrations.attio.webhooks import verify_signature
from app.main import app

client = TestClient(app)

SECRET = "test-webhook-secret"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ── verify_signature() ───────────────────────────────────────
def test_verify_signature_accepts_valid_signature(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_WEBHOOK_SECRET", SECRET)
    body = b'{"event_type":"list-entry.created"}'
    assert verify_signature(body, _sign(body)) is True


def test_verify_signature_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_WEBHOOK_SECRET", SECRET)
    body = b'{"event_type":"list-entry.created"}'
    assert verify_signature(body, "0" * 64) is False


def test_verify_signature_rejects_missing_header(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_WEBHOOK_SECRET", SECRET)
    body = b'{"event_type":"list-entry.created"}'
    assert verify_signature(body, "") is False


def test_verify_signature_rejects_when_secret_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_WEBHOOK_SECRET", "")
    body = b'{"event_type":"list-entry.created"}'
    assert verify_signature(body, _sign(body)) is False


def test_verify_signature_rejects_tampered_body(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_WEBHOOK_SECRET", SECRET)
    body = b'{"event_type":"list-entry.created"}'
    signature = _sign(body)
    tampered = b'{"event_type":"list-entry.deleted"}'
    assert verify_signature(tampered, signature) is False


# ── POST /api/v1/webhooks/attio ──────────────────────────────
def test_webhook_endpoint_accepts_valid_signature(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_WEBHOOK_SECRET", SECRET)
    payload = {"events": [{"event_type": "list-entry.created"}]}
    body = json.dumps(payload).encode()

    response = client.post(
        "/api/v1/webhooks/attio",
        content=body,
        headers={"attio-signature": _sign(body), "content-type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "events_received": 1}


def test_webhook_endpoint_accepts_legacy_header(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_WEBHOOK_SECRET", SECRET)
    payload = {"events": [{"event_type": "note.created"}]}
    body = json.dumps(payload).encode()

    response = client.post(
        "/api/v1/webhooks/attio",
        content=body,
        headers={"x-attio-signature": _sign(body), "content-type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "events_received": 1}


def test_webhook_endpoint_rejects_invalid_signature_without_crashing(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_WEBHOOK_SECRET", SECRET)
    payload = {"events": [{"event_type": "list-entry.created"}]}
    body = json.dumps(payload).encode()

    response = client.post(
        "/api/v1/webhooks/attio",
        content=body,
        headers={"attio-signature": "invalid", "content-type": "application/json"},
    )
    # Sempre 200 pra não gerar retry — mesma convenção do webhook Asaas.
    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "reason": "invalid signature"}


def test_webhook_endpoint_handles_bare_event_without_wrapper(monkeypatch):
    monkeypatch.setattr(settings, "ATTIO_WEBHOOK_SECRET", SECRET)
    payload = {"event_type": "list-entry.updated"}
    body = json.dumps(payload).encode()

    response = client.post(
        "/api/v1/webhooks/attio",
        content=body,
        headers={"attio-signature": _sign(body), "content-type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "events_received": 1}
