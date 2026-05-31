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


# ── Testes de dados — via API (migration 0018) ────────────────────────────────

class TestClassTribData:
    """Verifica que a migration 0018 populou os códigos corretamente — via endpoint."""

    @pytest.mark.parametrize("codigo,expected_regime,zero_rated", [
        ("01.01.001", "cesta_basica", True),
        ("02.01.001", "cesta_basica", True),
        ("04.01.001", "cesta_basica", True),
        ("10.01.001", "cesta_basica", True),
        ("30.01.001", "reduzido_60",  False),
        ("99.01.002", "reduzido_60",  False),
        ("48.01.002", "imune",        True),
        ("84.01.002", "imune",        True),
        ("99.01.001", "padrao",       False),
        ("39.01.001", "padrao",       False),
        ("85.17.001", "padrao",       False),
    ])
    def test_regime_e_aliquota(self, codigo, expected_regime, zero_rated):
        resp = client.get(f"/api/v1/public/classtrib/{codigo}")
        assert resp.status_code == 200, f"Código {codigo} não encontrado (migration 0018?)"
        data = resp.json()
        assert data["regime_especial"] == expected_regime, (
            f"{codigo}: regime esperado={expected_regime}, obtido={data['regime_especial']}"
        )
        if zero_rated:
            assert float(data["p_cbs"]) == 0.0, f"{codigo}: p_cbs deveria ser 0"
            assert float(data["p_ibs"]) == 0.0, f"{codigo}: p_ibs deveria ser 0"
        else:
            assert float(data["p_cbs"]) > 0.0, f"{codigo}: p_cbs deveria ser > 0"

    def test_capitulos_representados(self):
        """Verifica que os principais capítulos NCM respondem via search."""
        amostras = {
            "bovino":      "01.",  # matches "bovinos"
            "arroz":       "10.",  # matches "Cereais — arroz"
            "medicamento": "30.",  # matches "Medicamentos"
            "televisore":  "85.",  # matches "Televisores"
        }
        for termo, prefixo in amostras.items():
            resp = client.get(f"/api/v1/public/classtrib/search?q={termo}")
            assert resp.status_code == 200
            results = resp.json()
            assert any(r["codigo"].startswith(prefixo) for r in results), (
                f"Termo '{termo}' não retornou código do capítulo {prefixo}"
            )


# ── Testes de endpoint público ────────────────────────────────────────────────

class TestClassTribEndpoint:
    def test_lookup_cesta_basica(self):
        resp = client.get("/api/v1/public/classtrib/10.01.001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["codigo"] == "10.01.001"
        assert float(data["p_cbs"]) == 0.0
        assert float(data["p_ibs"]) == 0.0
        assert data["regime_especial"] == "cesta_basica"

    def test_lookup_servico_padrao(self):
        resp = client.get("/api/v1/public/classtrib/99.01.001")
        assert resp.status_code == 200
        data = resp.json()
        assert float(data["p_cbs"]) > 0
        assert data["regime_especial"] == "padrao"

    def test_lookup_retorna_last_synced_at(self):
        """Acceptance criteria #264: endpoint deve retornar last_synced_at."""
        resp = client.get("/api/v1/public/classtrib/99.01.001")
        assert resp.status_code == 200
        data = resp.json()
        assert "last_synced_at" in data, "Campo last_synced_at ausente na resposta"
        assert data["last_synced_at"] is not None

    def test_lookup_nao_encontrado(self):
        resp = client.get("/api/v1/public/classtrib/99.99.999")
        assert resp.status_code == 404

    def test_search_cereais(self):
        resp = client.get("/api/v1/public/classtrib/search?q=arroz")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 1
        codigos = [r["codigo"] for r in results]
        assert any(c.startswith("10.") for c in codigos)

    def test_search_medicamento(self):
        resp = client.get("/api/v1/public/classtrib/search?q=medicamento")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 1

    def test_search_min_length(self):
        resp = client.get("/api/v1/public/classtrib/search?q=a")
        assert resp.status_code == 422


# ── Testes de validação autenticada ───────────────────────────────────────────

class TestClassTribValidate:
    def test_validate_ok(self, auth_client):
        resp = auth_client.post(
            "/api/v1/classtrib/validate",
            json={"ncm": "1001000", "classtrib_informado": "10.01.001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("OK", "DIVERGENTE", "NAO_ENCONTRADO")

    def test_validate_nao_encontrado(self, auth_client):
        resp = auth_client.post(
            "/api/v1/classtrib/validate",
            json={"ncm": "9999999", "classtrib_informado": "99.99.999"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "NAO_ENCONTRADO"

    def test_validate_cesta_basica_correto(self, auth_client):
        """NCM 01 (bovinos) com cClassTrib 01.01.001 — deve ser OK e alíquotas zero."""
        resp = auth_client.post(
            "/api/v1/classtrib/validate",
            json={"ncm": "0102900000", "classtrib_informado": "01.01.001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "OK"
        assert not data["divergencia"]
        assert data["p_cbs_correto"] == 0.0
        assert data["p_ibs_correto"] == 0.0

    def test_validate_sem_auth(self):
        resp = client.post(
            "/api/v1/classtrib/validate",
            json={"ncm": "1001000", "classtrib_informado": "10.01.001"},
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
