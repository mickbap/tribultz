"""Tests for the Attio webhook signature verification and router —
PO-2026-07-CRM-001, fatia 7/12."""

from __future__ import annotations

import hashlib
import hmac

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


# ── Descomissionamento (ROUND 18-A, fatia 1) ─────────────────
# O endpoint POST /api/v1/webhooks/attio foi removido: o Attio deixou de fazer
# parte da arquitetura operacional. Os testes de aceitação do endpoint saíram
# junto com ele; sobra este guard, que falha se o router voltar a ser montado.
# `verify_signature` continua coberto acima e sai na fatia 2, com o módulo.
def test_webhook_attio_desmontado_retorna_404():
    for header in ("attio-signature", "x-attio-signature"):
        r = client.post(
            "/api/v1/webhooks/attio",
            content=b'{"events":[]}',
            headers={header: "qualquer", "content-type": "application/json"},
        )
        assert r.status_code == 404, (
            "router Attio voltou a ser montado — o descomissionamento do "
            "ROUND 18-A exige que esta rota nao exista"
        )


def test_nenhuma_rota_attio_registrada_no_app():
    from app.main import app as _app

    rotas = [getattr(r, "path", "") for r in _app.routes]
    assert not [p for p in rotas if "attio" in p.lower()], (
        "ha rota com 'attio' no path: %s" % [p for p in rotas if "attio" in p.lower()]
    )
