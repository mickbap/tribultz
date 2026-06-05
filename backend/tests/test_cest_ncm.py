"""Tests for NCM × CEST/ST lookup (#275 fase 2).

Covers:
- Data module (`app.data.cest_ncm`)
- Public endpoint `/api/v1/public/cest/{ncm}` + `/cest/_meta`
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.data.cest_ncm import is_st_ncm, lookup_ncm_st
from app.main import app

client = TestClient(app)


# ── Data module ──────────────────────────────────────────────────────────────

class TestLookupNcmSt:
    def test_st_ncm_refrigerante(self):
        """22021000 (refrigerantes) — bebidas não alcoólicas."""
        r = lookup_ncm_st("22021000")
        assert r["is_st"] is True
        assert r["matched_prefix"] == "2202"
        assert "bebidas_nao_alcoolicas" in r["segments"]

    def test_st_ncm_cigarro(self):
        r = lookup_ncm_st("24022000")
        assert r["is_st"] is True
        assert "fumo" in r["segments"]

    def test_st_ncm_with_dots_normalized(self):
        """Aceita NCM com pontos (formato pt-BR)."""
        r = lookup_ncm_st("2202.10.00")
        assert r["is_st"] is True
        assert r["matched_prefix"] == "2202"

    def test_non_st_ncm(self):
        """84713012 (equipamento de informática) não é ST."""
        r = lookup_ncm_st("84713012")
        assert r["is_st"] is False
        assert r["matched_prefix"] is None
        assert r["segments"] == []

    def test_empty_ncm(self):
        r = lookup_ncm_st("")
        assert r["is_st"] is False

    def test_longest_prefix_wins(self):
        """8544.49 deve bater contra material_eletrico, não só autopecas (8544)."""
        r = lookup_ncm_st("85444900")
        assert r["is_st"] is True
        # Tanto autopecas (prefix 8544) quanto material_eletrico (prefix 8544.49) batem
        assert "material_eletrico" in r["segments"]
        assert r["matched_prefix"] == "8544.49"  # mais específico

    def test_metadata_present(self):
        r = lookup_ncm_st("22020000")
        assert "source" in r
        assert "data_version" in r
        assert "Convênio ICMS 142/2018" in r["source"]

    def test_is_st_wrapper(self):
        assert is_st_ncm("22020000") is True
        assert is_st_ncm("84713012") is False
        assert is_st_ncm("") is False


# ── Endpoint ─────────────────────────────────────────────────────────────────

def test_endpoint_cest_st_ncm():
    resp = client.get("/api/v1/public/cest/22021000")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_st"] is True
    assert body["matched_prefix"] == "2202"
    assert "bebidas_nao_alcoolicas" in body["segments"]


def test_endpoint_cest_non_st_ncm():
    resp = client.get("/api/v1/public/cest/84713012")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_st"] is False
    assert body["segments"] == []


def test_endpoint_cest_meta():
    resp = client.get("/api/v1/public/cest/_meta")
    assert resp.status_code == 200
    body = resp.json()
    assert body["segments_count"] >= 10
    assert body["prefixes_count"] >= 60
    assert "bebidas_nao_alcoolicas" in body["segments"]
    assert "Convênio ICMS 142/2018" in body["source"]
