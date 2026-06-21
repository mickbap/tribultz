"""Tests for the deep health check endpoint (GET /health/ready and /health/deep).

All external probes (DB, Redis, Asaas, AI engine) are patched so the suite
runs without live infrastructure.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── Helper ────────────────────────────────────────────────────────────────────

def _patch_probes(db="ok", redis="ok", asaas="unconfigured", ai="unconfigured", hubspot="unconfigured", email="unconfigured"):
    """Context manager that patches all six probe functions."""
    return (
        patch("app.routers.health._probe_db",         return_value=db),
        patch("app.routers.health._probe_redis",       return_value=redis),
        patch("app.routers.health._probe_asaas",       return_value=asaas),
        patch("app.routers.health._probe_ai_engine",   return_value=ai),
        patch("app.routers.health._probe_hubspot",     return_value=hubspot),
        patch("app.routers.health._probe_email",       return_value=email),
    )


# ── Liveness (/health) ────────────────────────────────────────────────────────

class TestLiveness:
    def test_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_returns_status_ok(self):
        r = client.get("/health")
        assert r.json() == {"status": "ok"}

    def test_head_returns_200(self):
        r = client.head("/health")
        assert r.status_code == 200


# ── Readiness (/health/ready) ─────────────────────────────────────────────────

class TestReadiness:
    def test_all_ok_returns_ok(self):
        with (
            patch("app.routers.health._probe_db",         return_value="ok"),
            patch("app.routers.health._probe_redis",       return_value="ok"),
            patch("app.routers.health._probe_asaas",       return_value="ok"),
            patch("app.routers.health._probe_ai_engine",   return_value="ok"),
            patch("app.routers.health._probe_hubspot",     return_value="ok"),
            patch("app.routers.health._probe_email",       return_value="unconfigured"),
        ):
            r = client.get("/health/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["db"] == "ok"
        assert body["redis"] == "ok"
        assert body["asaas_api"] == "ok"
        assert body["ai_engine"] == "ok"
        assert body["hubspot"] == "ok"

    def test_hubspot_unreachable_returns_degraded(self):
        """HubSpot unreachable → degraded (optional service)."""
        with (
            patch("app.routers.health._probe_db",         return_value="ok"),
            patch("app.routers.health._probe_redis",       return_value="ok"),
            patch("app.routers.health._probe_asaas",       return_value="unconfigured"),
            patch("app.routers.health._probe_ai_engine",   return_value="unconfigured"),
            patch("app.routers.health._probe_hubspot",     return_value="unreachable"),
            patch("app.routers.health._probe_email",       return_value="unconfigured"),
        ):
            r = client.get("/health/ready")
        assert r.json()["status"] == "degraded"
        assert r.json()["hubspot"] == "unreachable"

    def test_hubspot_unconfigured_stays_ok(self):
        """HubSpot unconfigured (flag off) must NOT degrade status."""
        with (
            patch("app.routers.health._probe_db",         return_value="ok"),
            patch("app.routers.health._probe_redis",       return_value="ok"),
            patch("app.routers.health._probe_asaas",       return_value="ok"),
            patch("app.routers.health._probe_ai_engine",   return_value="ok"),
            patch("app.routers.health._probe_hubspot",     return_value="unconfigured"),
            patch("app.routers.health._probe_email",       return_value="unconfigured"),
        ):
            r = client.get("/health/ready")
        assert r.json()["status"] == "ok"
        assert r.json()["hubspot"] == "unconfigured"

    def test_unconfigured_optionals_still_ok(self):
        """Unconfigured optional services (Asaas, AI) must NOT degrade status."""
        with (
            patch("app.routers.health._probe_db",         return_value="ok"),
            patch("app.routers.health._probe_redis",       return_value="ok"),
            patch("app.routers.health._probe_asaas",       return_value="unconfigured"),
            patch("app.routers.health._probe_ai_engine",   return_value="unconfigured"),
            patch("app.routers.health._probe_hubspot",   return_value="unconfigured"),
            patch("app.routers.health._probe_email",       return_value="unconfigured"),
        ):
            r = client.get("/health/ready")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_db_unreachable_returns_error(self):
        with (
            patch("app.routers.health._probe_db",         return_value="unreachable"),
            patch("app.routers.health._probe_redis",       return_value="ok"),
            patch("app.routers.health._probe_asaas",       return_value="unconfigured"),
            patch("app.routers.health._probe_ai_engine",   return_value="unconfigured"),
            patch("app.routers.health._probe_hubspot",   return_value="unconfigured"),
            patch("app.routers.health._probe_email",       return_value="unconfigured"),
        ):
            r = client.get("/health/ready")
        assert r.status_code == 200  # HTTP always 200 — status field signals health
        assert r.json()["status"] == "error"
        assert r.json()["db"] == "unreachable"

    def test_redis_unreachable_returns_error(self):
        with (
            patch("app.routers.health._probe_db",         return_value="ok"),
            patch("app.routers.health._probe_redis",       return_value="unreachable"),
            patch("app.routers.health._probe_asaas",       return_value="unconfigured"),
            patch("app.routers.health._probe_ai_engine",   return_value="unconfigured"),
            patch("app.routers.health._probe_hubspot",   return_value="unconfigured"),
            patch("app.routers.health._probe_email",       return_value="unconfigured"),
        ):
            r = client.get("/health/ready")
        assert r.json()["status"] == "error"
        assert r.json()["redis"] == "unreachable"

    def test_optional_unreachable_returns_degraded(self):
        """Asaas or AI engine unreachable → degraded (not error)."""
        with (
            patch("app.routers.health._probe_db",         return_value="ok"),
            patch("app.routers.health._probe_redis",       return_value="ok"),
            patch("app.routers.health._probe_asaas",       return_value="unreachable"),
            patch("app.routers.health._probe_ai_engine",   return_value="unconfigured"),
            patch("app.routers.health._probe_hubspot",   return_value="unconfigured"),
            patch("app.routers.health._probe_email",       return_value="unconfigured"),
        ):
            r = client.get("/health/ready")
        assert r.json()["status"] == "degraded"
        assert r.json()["asaas_api"] == "unreachable"

    def test_response_contains_latency_ms(self):
        with (
            patch("app.routers.health._probe_db",         return_value="ok"),
            patch("app.routers.health._probe_redis",       return_value="ok"),
            patch("app.routers.health._probe_asaas",       return_value="unconfigured"),
            patch("app.routers.health._probe_ai_engine",   return_value="unconfigured"),
            patch("app.routers.health._probe_hubspot",   return_value="unconfigured"),
            patch("app.routers.health._probe_email",       return_value="unconfigured"),
        ):
            r = client.get("/health/ready")
        body = r.json()
        assert "latency_ms" in body
        assert isinstance(body["latency_ms"], int)
        assert body["latency_ms"] >= 0


# ── Deep alias (/health/deep) ─────────────────────────────────────────────────

class TestDeepAlias:
    def test_deep_mirrors_ready(self):
        """GET /health/deep must return identical structure as /health/ready."""
        with (
            patch("app.routers.health._probe_db",         return_value="ok"),
            patch("app.routers.health._probe_redis",       return_value="ok"),
            patch("app.routers.health._probe_asaas",       return_value="unconfigured"),
            patch("app.routers.health._probe_ai_engine",   return_value="unconfigured"),
            patch("app.routers.health._probe_hubspot",   return_value="unconfigured"),
            patch("app.routers.health._probe_email",       return_value="unconfigured"),
        ):
            r_ready = client.get("/health/ready")
            r_deep  = client.get("/health/deep")

        # Both must have same structure (latency_ms may differ slightly)
        for key in ("status", "db", "redis", "asaas_api", "ai_engine"):
            assert r_ready.json()[key] == r_deep.json()[key]


# ── Probe unit tests ──────────────────────────────────────────────────────────

class TestDbProbe:
    def test_probe_ok_when_db_responds(self):
        mock_session = MagicMock()
        with patch("app.routers.health.SessionLocal", return_value=mock_session):
            from app.routers.health import _probe_db
            result = _probe_db()
        assert result == "ok"

    def test_probe_unreachable_on_exception(self):
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("connection refused")
        with patch("app.routers.health.SessionLocal", return_value=mock_session):
            from app.routers.health import _probe_db
            result = _probe_db()
        assert result == "unreachable"


class TestRedisProbe:
    def test_probe_ok_when_ping_succeeds(self):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        with patch("app.routers.health.redis_lib.from_url", return_value=mock_client):
            from app.routers.health import _probe_redis
            result = _probe_redis()
        assert result == "ok"

    def test_probe_unreachable_on_connection_error(self):
        with patch("app.routers.health.redis_lib.from_url", side_effect=Exception("refused")):
            from app.routers.health import _probe_redis
            result = _probe_redis()
        assert result == "unreachable"


class TestAsaasProbe:
    def test_unconfigured_when_no_api_key(self):
        with patch("app.routers.health.settings") as mock_cfg:
            mock_cfg.ASAAS_API_KEY = ""
            mock_cfg.ASAAS_ENVIRONMENT = "sandbox"
            from app.routers.health import _probe_asaas
            result = _probe_asaas()
        assert result == "unconfigured"

    def test_ok_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with (
            patch("app.routers.health.settings") as mock_cfg,
            patch("app.routers.health.httpx.get", return_value=mock_resp),
        ):
            mock_cfg.ASAAS_API_KEY = "test-key"
            mock_cfg.ASAAS_ENVIRONMENT = "sandbox"
            from app.routers.health import _probe_asaas
            result = _probe_asaas()
        assert result == "ok"

    def test_uses_production_v3_base(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with (
            patch("app.routers.health.settings") as mock_cfg,
            patch("app.routers.health.httpx.get", return_value=mock_resp) as mock_get,
        ):
            mock_cfg.ASAAS_API_KEY = "test-key"
            mock_cfg.ASAAS_ENVIRONMENT = "production"
            from app.routers.health import _probe_asaas
            result = _probe_asaas()
        assert result == "ok"
        assert mock_get.call_args.args[0] == "https://api.asaas.com/v3/finance/balance"

    def test_ok_on_401(self):
        """401 = wrong key but API is reachable → 'ok' for health purposes."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with (
            patch("app.routers.health.settings") as mock_cfg,
            patch("app.routers.health.httpx.get", return_value=mock_resp),
        ):
            mock_cfg.ASAAS_API_KEY = "bad-key"
            mock_cfg.ASAAS_ENVIRONMENT = "sandbox"
            from app.routers.health import _probe_asaas
            result = _probe_asaas()
        assert result == "ok"

    def test_unreachable_on_network_error(self):
        with (
            patch("app.routers.health.settings") as mock_cfg,
            patch("app.routers.health.httpx.get", side_effect=Exception("timeout")),
        ):
            mock_cfg.ASAAS_API_KEY = "test-key"
            mock_cfg.ASAAS_ENVIRONMENT = "sandbox"
            from app.routers.health import _probe_asaas
            result = _probe_asaas()
        assert result == "unreachable"


class TestAIEngineProbe:
    def test_unconfigured_when_no_key(self):
        with patch("app.routers.health.settings") as mock_cfg:
            mock_cfg.OPENROUTER_API_KEY = ""
            mock_cfg.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
            from app.routers.health import _probe_ai_engine
            result = _probe_ai_engine()
        assert result == "unconfigured"

    def test_ok_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with (
            patch("app.routers.health.settings") as mock_cfg,
            patch("app.routers.health.httpx.get", return_value=mock_resp),
        ):
            mock_cfg.OPENROUTER_API_KEY = "test-key"
            mock_cfg.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
            from app.routers.health import _probe_ai_engine
            result = _probe_ai_engine()
        assert result == "ok"

    def test_unreachable_on_timeout(self):
        with (
            patch("app.routers.health.settings") as mock_cfg,
            patch("app.routers.health.httpx.get", side_effect=Exception("timeout")),
        ):
            mock_cfg.OPENROUTER_API_KEY = "test-key"
            mock_cfg.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
            from app.routers.health import _probe_ai_engine
            result = _probe_ai_engine()
        assert result == "unreachable"


# ── HubSpot probe unit (#293) ────────────────────────────────────────────────

class TestProbeHubspot:
    def test_disabled_returns_unconfigured(self):
        with patch("app.routers.health.settings") as mock_cfg:
            mock_cfg.HUBSPOT_ENABLED = False
            mock_cfg.HUBSPOT_PRIVATE_APP_TOKEN = "any-token"
            from app.routers.health import _probe_hubspot
            assert _probe_hubspot() == "unconfigured"

    def test_no_token_returns_unconfigured(self):
        with patch("app.routers.health.settings") as mock_cfg:
            mock_cfg.HUBSPOT_ENABLED = True
            mock_cfg.HUBSPOT_PRIVATE_APP_TOKEN = ""
            from app.routers.health import _probe_hubspot
            assert _probe_hubspot() == "unconfigured"

    def test_200_returns_ok(self):
        mock_resp = MagicMock(status_code=200)
        with (
            patch("app.routers.health.settings") as mock_cfg,
            patch("app.routers.health.httpx.get", return_value=mock_resp),
        ):
            mock_cfg.HUBSPOT_ENABLED = True
            mock_cfg.HUBSPOT_PRIVATE_APP_TOKEN = "test-token"
            mock_cfg.HUBSPOT_API_BASE_URL = "https://api.hubapi.com"
            from app.routers.health import _probe_hubspot
            assert _probe_hubspot() == "ok"

    def test_401_returns_ok_gateway_reachable(self):
        """Token inválido mas API gateway respondeu — consideramos reachable."""
        mock_resp = MagicMock(status_code=401)
        with (
            patch("app.routers.health.settings") as mock_cfg,
            patch("app.routers.health.httpx.get", return_value=mock_resp),
        ):
            mock_cfg.HUBSPOT_ENABLED = True
            mock_cfg.HUBSPOT_PRIVATE_APP_TOKEN = "bad-token"
            mock_cfg.HUBSPOT_API_BASE_URL = "https://api.hubapi.com"
            from app.routers.health import _probe_hubspot
            assert _probe_hubspot() == "ok"

    def test_500_returns_degraded(self):
        mock_resp = MagicMock(status_code=500)
        with (
            patch("app.routers.health.settings") as mock_cfg,
            patch("app.routers.health.httpx.get", return_value=mock_resp),
        ):
            mock_cfg.HUBSPOT_ENABLED = True
            mock_cfg.HUBSPOT_PRIVATE_APP_TOKEN = "test-token"
            mock_cfg.HUBSPOT_API_BASE_URL = "https://api.hubapi.com"
            from app.routers.health import _probe_hubspot
            assert _probe_hubspot() == "degraded"

    def test_timeout_returns_unreachable(self):
        with (
            patch("app.routers.health.settings") as mock_cfg,
            patch("app.routers.health.httpx.get", side_effect=Exception("timeout")),
        ):
            mock_cfg.HUBSPOT_ENABLED = True
            mock_cfg.HUBSPOT_PRIVATE_APP_TOKEN = "test-token"
            mock_cfg.HUBSPOT_API_BASE_URL = "https://api.hubapi.com"
            from app.routers.health import _probe_hubspot
            assert _probe_hubspot() == "unreachable"


# ── Email/Resend readiness (#293) ─────────────────────────────────────────────

class TestEmailReadiness:
    def test_email_unreachable_returns_degraded(self):
        with (
            patch("app.routers.health._probe_db",         return_value="ok"),
            patch("app.routers.health._probe_redis",       return_value="ok"),
            patch("app.routers.health._probe_asaas",       return_value="unconfigured"),
            patch("app.routers.health._probe_ai_engine",   return_value="unconfigured"),
            patch("app.routers.health._probe_hubspot",     return_value="unconfigured"),
            patch("app.routers.health._probe_email",       return_value="unreachable"),
        ):
            r = client.get("/health/ready")
        assert r.json()["status"] == "degraded"
        assert r.json()["email"] == "unreachable"

    def test_email_unconfigured_stays_ok(self):
        with (
            patch("app.routers.health._probe_db",         return_value="ok"),
            patch("app.routers.health._probe_redis",       return_value="ok"),
            patch("app.routers.health._probe_asaas",       return_value="ok"),
            patch("app.routers.health._probe_ai_engine",   return_value="ok"),
            patch("app.routers.health._probe_hubspot",     return_value="ok"),
            patch("app.routers.health._probe_email",       return_value="unconfigured"),
        ):
            r = client.get("/health/ready")
        assert r.json()["status"] == "ok"
        assert r.json()["email"] == "unconfigured"


# ── Email probe unit (#293) ───────────────────────────────────────────────────

class TestProbeEmail:
    def test_disabled_returns_unconfigured(self):
        with patch("app.routers.health.settings") as cfg:
            cfg.EMAIL_VERIFICATION_ENABLED = False
            cfg.SMTP_HOST = "smtp.resend.com"
            from app.routers.health import _probe_email
            assert _probe_email() == "unconfigured"

    def test_no_host_returns_unconfigured(self):
        with patch("app.routers.health.settings") as cfg:
            cfg.EMAIL_VERIFICATION_ENABLED = True
            cfg.SMTP_HOST = ""
            from app.routers.health import _probe_email
            assert _probe_email() == "unconfigured"

    def test_ehlo_ok_returns_ok(self):
        mock_server = MagicMock()
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.__exit__ = MagicMock(return_value=False)
        with (
            patch("app.routers.health.settings") as cfg,
            patch("app.routers.health.smtplib.SMTP", return_value=mock_smtp),
        ):
            cfg.EMAIL_VERIFICATION_ENABLED = True
            cfg.SMTP_HOST = "smtp.resend.com"
            cfg.SMTP_PORT = 587
            from app.routers.health import _probe_email
            assert _probe_email() == "ok"
        mock_server.ehlo.assert_called_once()

    def test_connection_error_returns_unreachable(self):
        with (
            patch("app.routers.health.settings") as cfg,
            patch("app.routers.health.smtplib.SMTP", side_effect=OSError("connection refused")),
        ):
            cfg.EMAIL_VERIFICATION_ENABLED = True
            cfg.SMTP_HOST = "smtp.resend.com"
            cfg.SMTP_PORT = 587
            from app.routers.health import _probe_email
            assert _probe_email() == "unreachable"
