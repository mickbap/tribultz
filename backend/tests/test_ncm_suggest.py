"""POST /api/v1/public/ncm/suggest — cClassTrib nunca em taxonomia de produto (ORDER fix)."""

from __future__ import annotations

import contextlib
import re
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PRODUCT_TAX = re.compile(r"\d{2}\.\d{2}\.\d{3}")  # ex.: 01.01.001 (taxonomia antiga, proibida)


def _patches(ncm="84713012", conf=0.9):
    return [
        patch("app.routers.ncm_suggest._rate_check", return_value=None),
        patch("app.routers.ncm_suggest._cache_get", return_value=None),
        patch("app.routers.ncm_suggest._cache_set", return_value=None),
        patch(
            "app.routers.ncm_suggest._llm_classify",
            return_value={"ncm": ncm, "ncm_descricao": "Produto X", "confidence": conf},
        ),
    ]


def _post(desc="Notebook 16GB", ncm="84713012", conf=0.9):
    with contextlib.ExitStack() as stack:
        for p in _patches(ncm=ncm, conf=conf):
            stack.enter_context(p)
        return client.post("/api/v1/public/ncm/suggest", json={"descricao": desc})


class TestNcmSuggestCClassTrib:
    def test_nunca_retorna_taxonomia_de_produto(self):
        """RF-A1: nenhum valor da resposta no formato NN.NN.NNN."""
        r = _post()
        assert r.status_code == 200
        assert not PRODUCT_TAX.search(r.text), f"taxonomia de produto vazou: {r.text}"

    def test_cclasstrib_null_com_fallback_honesto(self):
        """RF-A1/A3: cClassTrib null + status 'requer_validacao' (sem palpite confiante)."""
        body = _post().json()
        assert body["cClassTrib"] is None
        assert body["cclasstrib_status"] == "requer_validacao"
        assert body["cclasstrib_candidatos"] == []

    def test_ncm_multi_mapeada_tambem_fallback_ate_mapeamento(self):
        """RF-A2: NCM multi (ex. 9619.00.00) ainda em fallback até o mapeamento (#313) — sem veredito."""
        body = _post(desc="Absorvente higiênico", ncm="96190000").json()
        assert body["cClassTrib"] is None
        assert body["cclasstrib_status"] == "requer_validacao"

    def test_contrato_ncm_preservado(self):
        """RF-A4: campos do contrato público preservados (ncm, confidence, aviso)."""
        body = _post().json()
        assert body["ncm"] == "84713012"
        assert "confidence" in body and "aviso" in body and "rate_source" in body

    def test_baixa_confianca_mantem_aviso(self):
        body = _post(conf=0.4).json()
        assert body["aviso"] is not None
