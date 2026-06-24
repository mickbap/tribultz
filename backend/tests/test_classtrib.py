"""Testes de regressão para cClassTrib — migration 0018 + endpoint + sync task.

Verifica que:
- Os códigos essenciais (cesta básica, padrão, serviços) estão presentes na DB
- As alíquotas estão corretas por regime
- O endpoint /public/classtrib/{codigo} retorna last_synced_at
- O endpoint /public/classtrib/search retorna resultados relevantes
- O endpoint /classtrib/validate detecta divergência de NCM × cClassTrib
- sync_classtrib_svrs trata 403 de forma graceful (sem lançar exceção)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_FAKE_USER_ID = UUID("00000000-0000-0000-0000-000000000099")
_FAKE_TENANT_ID = UUID("00000000-0000-0000-0000-000000000099")


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def auth_client():
    """TestClient com dependency_override para get_current_user — sem DB real."""
    from app.api.deps import get_current_user
    from app.models.auth import User

    fake_user = User(
        id=_FAKE_USER_ID,
        tenant_id=_FAKE_TENANT_ID,
        email="test@classtrib.test",
        full_name="Test User",
        password_hash="x",
        role="admin",
        account_type="empresa",
        is_active=True,
        email_verified=True,
    )

    def _override():
        return fake_user

    app.dependency_overrides[get_current_user] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user, None)


# ── Testes de dados — via API (migration 0020: 156 cClassTrib de 6 dígitos) ───

class TestClassTribData:
    """A migration 0020 re-seedou os 156 cClassTrib de 6 dígitos (fonte pública SVRS)."""

    @pytest.mark.parametrize("codigo,regime,zero", [
        ("000001", "padrao", False),
        ("200001", "reducao_integral", True),
        ("400001", "isencao", True),
        ("410001", "imunidade", True),
        ("011001", "reducao_60", False),
    ])
    def test_regime_e_aliquota(self, codigo, regime, zero):
        resp = client.get(f"/api/v1/public/classtrib/{codigo}")
        assert resp.status_code == 200, f"{codigo} não encontrado (migration 0020?)"
        data = resp.json()
        assert data["regime_especial"] == regime
        if zero:
            assert float(data["p_cbs"]) == 0.0 and float(data["p_ibs"]) == 0.0
        else:
            assert float(data["p_cbs"]) > 0.0

    def test_padrao_usa_aliquota_de_referencia_plena(self):
        """000001 (padrão) → alíquota de REFERÊNCIA PLENA (8,8 / 17,7), não a de teste 2026."""
        data = client.get("/api/v1/public/classtrib/000001").json()
        assert float(data["p_cbs"]) == 8.8
        assert float(data["p_ibs"]) == 17.7

    def test_search_por_termo_da_descricao(self):
        resp = client.get("/api/v1/public/classtrib/search?q=serviços")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ── Testes de endpoint público ────────────────────────────────────────────────

class TestClassTribEndpoint:
    def test_lookup_isencao(self):
        data = client.get("/api/v1/public/classtrib/400001").json()
        assert data["codigo"] == "400001"
        assert float(data["p_cbs"]) == 0.0
        assert data["regime_especial"] == "isencao"

    def test_lookup_padrao(self):
        data = client.get("/api/v1/public/classtrib/000001").json()
        assert float(data["p_cbs"]) > 0
        assert data["regime_especial"] == "padrao"

    def test_lookup_retorna_last_synced_at(self):
        """Acceptance criteria #264: endpoint deve retornar last_synced_at."""
        data = client.get("/api/v1/public/classtrib/000001").json()
        assert "last_synced_at" in data and data["last_synced_at"] is not None

    def test_lookup_nao_encontrado(self):
        assert client.get("/api/v1/public/classtrib/999999").status_code == 404

    def test_taxonomia_de_produto_aposentada(self):
        """Código no formato antigo de produto (01.01.001) não deve mais existir."""
        assert client.get("/api/v1/public/classtrib/10.01.001").status_code == 404

    def test_search_min_length(self):
        assert client.get("/api/v1/public/classtrib/search?q=a").status_code == 422


# ── Testes de validação autenticada (NCM × cClassTrib via mapeamento) ──────────

class TestClassTribValidate:
    def test_validate_ok_candidato_oficial(self, auth_client):
        # NCM 0201.10.00 → candidato oficial 200003 (mapeamento de anexos SVRS)
        resp = auth_client.post(
            "/api/v1/classtrib/validate",
            json={"ncm": "02011000", "classtrib_informado": "200003"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "OK" and not data["divergencia"]

    def test_validate_divergente(self, auth_client):
        # 000001 existe mas NÃO é candidato da NCM 0201.10.00 → DIVERGENTE
        resp = auth_client.post(
            "/api/v1/classtrib/validate",
            json={"ncm": "02011000", "classtrib_informado": "000001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DIVERGENTE" and data["divergencia"]
        assert data["classtrib_sugerido"] == "200003"

    def test_validate_nao_encontrado(self, auth_client):
        resp = auth_client.post(
            "/api/v1/classtrib/validate",
            json={"ncm": "02011000", "classtrib_informado": "999999"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "NAO_ENCONTRADO"

    def test_validate_sem_auth(self):
        resp = client.post(
            "/api/v1/classtrib/validate",
            json={"ncm": "02011000", "classtrib_informado": "200003"},
        )
        assert resp.status_code == 401


# ── Testes do task sync ───────────────────────────────────────────────────────

class TestSyncClasstribSvrs:
    def test_svrs_403_retorna_graceful(self):
        """403 da SVRS não deve lançar exceção — retorna dict com reason."""
        from app.tasks.task_i_compliance import sync_classtrib_svrs

        mock_resp = MagicMock()
        mock_resp.status_code = 403

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            result = sync_classtrib_svrs()

        assert result["synced"] == 0
        assert result.get("reason") == "svrs_auth_required"
        assert result.get("status_code") == 403

    def test_svrs_network_error_retorna_graceful(self):
        """Erro de rede não deve lançar exceção."""
        import httpx
        from app.tasks.task_i_compliance import sync_classtrib_svrs

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = httpx.ConnectError("connection refused")
            mock_client_cls.return_value = mock_client

            result = sync_classtrib_svrs()

        assert result["synced"] == 0
        assert "error" in result


class TestSvrsAuthHeaders:
    """#313 credential-ready: Authorization Bearer só quando CLASSTRIB_API_TOKEN setado."""

    def test_sem_token_sem_authorization(self, monkeypatch):
        from app.config import settings
        from app.services.classtrib_service import svrs_auth_headers
        monkeypatch.setattr(settings, "CLASSTRIB_API_TOKEN", "")
        h = svrs_auth_headers()
        assert "Authorization" not in h
        assert h["Accept"] == "application/json"
        assert "Tribultz" in h["User-Agent"]

    def test_com_token_envia_bearer(self, monkeypatch):
        from app.config import settings
        from app.services.classtrib_service import svrs_auth_headers
        monkeypatch.setattr(settings, "CLASSTRIB_API_TOKEN", "  tok-abc  ")
        h = svrs_auth_headers()
        assert h["Authorization"] == "Bearer tok-abc"  # trim aplicado

    def test_sync_task_envia_authorization_quando_token(self, monkeypatch):
        """O sync task injeta o header Authorization quando o token está configurado."""
        from app.config import settings
        from app.tasks.task_i_compliance import sync_classtrib_svrs
        monkeypatch.setattr(settings, "CLASSTRIB_API_TOKEN", "tok-xyz")

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value = mock_client
            sync_classtrib_svrs()

        _, kwargs = mock_client_cls.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer tok-xyz"
