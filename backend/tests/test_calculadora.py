"""Tests for the Calculadora CBS/IBS endpoints."""

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.data.uf_rates import UF_RATES
from app.main import app
from app.routers.calculadora import _rate_limiter, _daily_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_calc_rate_limiters():
    """Clear rate limiter state between tests."""
    for rl in (_rate_limiter, _daily_limiter):
        rl._memory_store.clear()
        if rl.redis is not None:
            try:
                for prefix in ("ratelimit:calc:", "ratelimit:calc_daily:"):
                    for suffix in ("testclient", "127.0.0.1", "unknown"):
                        rl.redis.delete(f"{prefix}{suffix}")
            except Exception:
                pass
    yield
    for rl in (_rate_limiter, _daily_limiter):
        rl._memory_store.clear()


# ── Public calculator endpoint ───────────────────────────────────────────────

class TestPublicCalculadora:
    def test_basic_calculation_sp(self):
        resp = client.post(
            "/api/v1/public/calculadora/regime-geral",
            json={
                "uf_destino": "SP",
                "base_value": "1000.00",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["vBC"] == "1000.00"
        assert float(data["vCBS"]) == 88.00  # 1000 × 0.0880
        assert float(data["total_tributos"]) > 0
        assert "<IBSCBS>" in data["xml_snippet"]
        assert "<CST>000</CST>" in data["xml_snippet"]
        assert "data_policy" in data
        assert "upgrade_cta" in data

    def test_with_ncm(self):
        resp = client.post(
            "/api/v1/public/calculadora/regime-geral",
            json={
                "uf_destino": "RJ",
                "base_value": "500.00",
                "ncm_code": "84713012",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate_source"] == "uf_default"  # ch.84 has no override
        assert float(data["total_tributos"]) > 0

    def test_cesta_basica_zero_rate(self):
        resp = client.post(
            "/api/v1/public/calculadora/regime-geral",
            json={
                "uf_destino": "SP",
                "base_value": "100.00",
                "ncm_code": "02011000",  # Meat — cesta básica
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate_source"] == "ncm"
        assert float(data["vCBS"]) == 0.00
        assert float(data["total_tributos"]) == 0.00

    def test_exempt_cst_070(self):
        resp = client.post(
            "/api/v1/public/calculadora/regime-geral",
            json={
                "uf_destino": "MG",
                "base_value": "1000.00",
                "cst": "070",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cst"] == "070"
        assert float(data["total_tributos"]) == 0.00
        assert "<gIBSCBS>" not in data["xml_snippet"]

    def test_reduced_cst_001(self):
        resp = client.post(
            "/api/v1/public/calculadora/regime-geral",
            json={
                "uf_destino": "SP",
                "base_value": "1000.00",
                "cst": "001",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # Reduced = 60% of normal CBS (88.00 × 0.6 = 52.80)
        assert float(data["vCBS"]) == 52.80

    def test_with_quantity(self):
        resp = client.post(
            "/api/v1/public/calculadora/regime-geral",
            json={
                "uf_destino": "SP",
                "base_value": "200.00",
                "quantity": "3",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["vBC"] == "600.00"  # 200 × 3

    def test_invalid_uf_returns_422(self):
        resp = client.post(
            "/api/v1/public/calculadora/regime-geral",
            json={
                "uf_destino": "XX",
                "base_value": "1000.00",
            },
        )
        assert resp.status_code == 422

    def test_negative_base_returns_422(self):
        resp = client.post(
            "/api/v1/public/calculadora/regime-geral",
            json={
                "uf_destino": "SP",
                "base_value": "-100.00",
            },
        )
        assert resp.status_code == 422

    def test_invalid_ncm_returns_422(self):
        resp = client.post(
            "/api/v1/public/calculadora/regime-geral",
            json={
                "uf_destino": "SP",
                "base_value": "100.00",
                "ncm_code": "1234",
            },
        )
        assert resp.status_code == 422

    def test_invalid_cst_returns_422(self):
        resp = client.post(
            "/api/v1/public/calculadora/regime-geral",
            json={
                "uf_destino": "SP",
                "base_value": "100.00",
                "cst": "999",
            },
        )
        assert resp.status_code == 422

    @patch("app.routers.calculadora._rate_limiter")
    def test_rate_limit_429(self, mock_limiter):
        from fastapi import HTTPException
        mock_limiter.check_or_raise.side_effect = HTTPException(
            status_code=429, detail="Limite excedido",
        )
        resp = client.post(
            "/api/v1/public/calculadora/regime-geral",
            json={"uf_destino": "SP", "base_value": "100.00"},
        )
        assert resp.status_code == 429

    @pytest.mark.parametrize(
        ("uf", "expected"),
        sorted(UF_RATES.items()),
        ids=sorted(UF_RATES.keys()),
    )
    def test_all_states_regression_matrix(self, uf, expected):
        expected_total_rate = (
            expected["cbs_rate"]
            + expected["ibs_uf_rate"]
            + expected["ibs_mun_rate"]
        )

        resp = client.post(
            "/api/v1/public/calculadora/regime-geral",
            json={
                "uf_destino": uf,
                "base_value": "1000.00",
                "quantity": "1",
                "cst": "000",
            },
        )

        assert resp.status_code == 200

        data = resp.json()
        assert data["pCBS"] == str(expected["cbs_rate"])
        assert data["pIBSUF"] == str(expected["ibs_uf_rate"])
        assert data["pIBSMun"] == str(expected["ibs_mun_rate"])
        assert data["aliquota_efetiva"] == str(expected_total_rate)
        assert data["rate_source"] == "uf_default"
        assert "<IBSCBS>" in data["xml_snippet"]
        assert "<CST>000</CST>" in data["xml_snippet"]


# ── UF rates endpoint ────────────────────────────────────────────────────────

class TestUfRatesEndpoint:
    def test_returns_27_states(self):
        resp = client.get("/api/v1/public/calculadora/uf-rates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 27
        assert "SP" in data
        assert "uf_name" in data["SP"]
        assert "cbs_rate" in data["SP"]
        assert "ibs_total" in data["SP"]

    def test_matches_reference_rate_table(self):
        resp = client.get("/api/v1/public/calculadora/uf-rates")
        assert resp.status_code == 200

        data = resp.json()
        assert set(data) == set(UF_RATES)

        for uf, expected in UF_RATES.items():
            assert data[uf]["uf_name"] == expected["uf_name"]
            assert data[uf]["cbs_rate"] == str(expected["cbs_rate"])
            assert data[uf]["ibs_uf_rate"] == str(expected["ibs_uf_rate"])
            assert data[uf]["ibs_mun_rate"] == str(expected["ibs_mun_rate"])
            assert data[uf]["ibs_total"] == str(
                expected["ibs_uf_rate"] + expected["ibs_mun_rate"]
            )


# ── CST list endpoint ────────────────────────────────────────────────────────

class TestCstListEndpoint:
    def test_returns_14_csts(self):
        resp = client.get("/api/v1/public/calculadora/cst-list")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 14
        codes = {item["code"] for item in data}
        assert "000" in codes
        assert "070" in codes
