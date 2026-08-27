"""POST /api/v1/public/ncm/suggest — candidatos NCM→cClassTrib (Order A) + nunca taxonomia de produto."""

from __future__ import annotations

import contextlib
import re
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
PRODUCT_TAX = re.compile(r"\d{2}\.\d{2}\.\d{3}")  # taxonomia antiga proibida (01.01.001)


def _patches(ncm, conf=0.9):
    return [
        patch("app.routers.ncm_suggest._rate_check", return_value=None),
        patch("app.routers.ncm_suggest._cache_get", return_value=None),
        patch("app.routers.ncm_suggest._cache_set", return_value=None),
        patch(
            "app.routers.ncm_suggest._llm_classify",
            return_value={"ncm": ncm, "ncm_descricao": "Produto", "confidence": conf},
        ),
    ]


def _post(ncm, desc="produto", conf=0.9):
    with contextlib.ExitStack() as stack:
        for p in _patches(ncm, conf):
            stack.enter_context(p)
        return client.post("/api/v1/public/ncm/suggest", json={"descricao": desc})


class TestCandidatos:
    def test_multi_mapeada_retorna_candidatos_sem_veredito(self):
        b = _post("96190000", "absorvente").json()
        assert b["cClassTrib"] is None  # nunca veredito único quando a NCM admite vários
        assert b["cclasstrib_status"] == "multiplos"
        assert len(b["cclasstrib_candidatos"]) >= 2
        cand = b["cclasstrib_candidatos"][0]
        assert re.fullmatch(r"\d{6}", cand["codigo"]) and cand["base_legal"]

    def test_candidato_unico_nao_vira_veredito(self):
        """#672 Fase 2: um candidato só é delimitação, não determinação.

        A NCM 0201.10.00 consta de um anexo apenas (Anexo I, cesta básica) — e o
        título desse anexo condiciona o tratamento à destinação ("PRODUTOS
        DESTINADOS À ALIMENTAÇÃO HUMANA"). Destinação é atributo da operação, que
        este endpoint não recebe. O candidato vem na lista; o veredito, não.
        """
        b = _post("02011000", "carne bovina").json()
        assert b["cclasstrib_status"] == "candidato_unico"
        assert b["cClassTrib"] is None
        assert [c["codigo"] for c in b["cclasstrib_candidatos"]] == ["200003"]

    def test_sem_mapeamento_fallback_honesto(self):
        b = _post("84713012", "notebook").json()
        assert b["cClassTrib"] is None
        assert b["cclasstrib_status"] == "requer_validacao"
        assert b["cclasstrib_candidatos"] == []

    def test_nunca_taxonomia_de_produto(self):
        for ncm in ("96190000", "02011000", "84713012"):
            assert not PRODUCT_TAX.search(_post(ncm).text), ncm
