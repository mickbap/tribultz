"""POST /api/v1/public-api/classify (pago) — candidatos + cobra só quando classifica (Order A)."""

from __future__ import annotations

import re
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.routers.public_api import _resolve_api_key

client = TestClient(app)
PRODUCT_TAX = re.compile(r"\d{2}\.\d{2}\.\d{3}")


def _fake_key(balance=100):
    k = MagicMock()
    k.id = "key-1"
    k.credits_balance = balance
    return k


def _fake_result():
    r = MagicMock()
    r.cst = "000"
    r.vBC = Decimal("100.00")
    r.vCBS = Decimal("8.80")
    r.vIBS = Decimal("17.70")
    r.total_tributos = Decimal("26.50")
    r.aliquota_efetiva = Decimal("0.2650")
    r.xml_snippet = "<IBSCBS><CST>000</CST></IBSCBS>"
    return r


class TestClassifyPago:
    def setup_method(self):
        app.dependency_overrides[_resolve_api_key] = lambda: _fake_key(100)
        app.dependency_overrides[get_db] = lambda: MagicMock()

    def teardown_method(self):
        app.dependency_overrides.clear()

    def _post(self, ncm):
        with patch("app.routers.public_api.calculate_full", return_value=_fake_result()):
            return client.post(
                "/api/v1/public-api/classify",
                headers={"X-API-Key": "x"},
                json={"ncm": ncm, "uf_destino": "SP", "cst": "000", "base_value": "100.00"},
            )

    def test_multi_cobra_e_retorna_candidatos(self):
        b = self._post("01022110").json()  # multi-mapeada, TIPI-válida
        assert b["cclasstrib_status"] == "multiplos"
        assert len(b["cclasstrib_candidatos"]) >= 2
        assert b["credits_used"] == 1 and b["credits_remaining"] == 99

    def test_unico_cobra(self):
        b = self._post("02011000").json()
        assert b["cClassTrib"] == "200003"
        assert b["credits_used"] == 1

    def test_sem_mapeamento_nao_cobra(self):
        b = self._post("84713012").json()  # notebook — sem mapeamento de anexo
        assert b["cClassTrib"] is None
        assert b["cclasstrib_status"] == "requer_validacao"
        assert b["credits_used"] == 0 and b["credits_remaining"] == 100

    def test_nunca_taxonomia_de_produto(self):
        assert not PRODUCT_TAX.search(self._post("01022110").text)

    def test_calculo_cbs_ibs_entregue(self):
        b = self._post("84713012").json()
        assert b["vCBS"] == "8.80" and b["vIBS"] == "17.70"
