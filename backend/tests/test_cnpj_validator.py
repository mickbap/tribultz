"""CNPJ alfanumérico (RFB, produção 27/07/2026) — #514.

Formato oficial: 14 caracteres — 12 alfanuméricos (raiz + ordem do
estabelecimento) + 2 dígitos verificadores, que permanecem numéricos.
Regressão coberta aqui: o validador antigo assumia 14 dígitos puramente
numéricos e rejeitava (ou descartava letras de) um CNPJ alfanumérico legítimo.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.cnpj_validator import is_valid_cnpj_format, normalize_cnpj, validate_cnpj


def test_cnpj_numerico_tradicional_valido():
    assert is_valid_cnpj_format("12345678000199")


def test_cnpj_numerico_formatado_com_pontuacao_valido():
    assert is_valid_cnpj_format("12.345.678/0001-99")


def test_cnpj_alfanumerico_valido():
    assert is_valid_cnpj_format("12ABC34501DE35")


def test_cnpj_alfanumerico_formatado_com_pontuacao_valido():
    assert is_valid_cnpj_format("12.ABC.345/01DE-35")


def test_cnpj_alfanumerico_minusculo_normaliza_para_maiusculo():
    assert is_valid_cnpj_format("12abc34501de35")


def test_cnpj_digitos_verificadores_devem_ser_numericos():
    assert not is_valid_cnpj_format("12ABC34501DEAB")  # últimos 2 não numéricos


def test_cnpj_tamanho_errado_invalido():
    assert not is_valid_cnpj_format("1234567800019")  # 13 chars
    assert not is_valid_cnpj_format("123456780001999")  # 15 chars


def test_normalize_cnpj_remove_pontuacao_e_uppercase():
    assert normalize_cnpj("12.abc.345/01de-35") == "12ABC34501DE35"


@pytest.mark.asyncio
async def test_validate_cnpj_formato_invalido_nao_chama_api_externa():
    with patch("app.services.cnpj_validator._try_brasilapi", new_callable=AsyncMock) as mock_api:
        result = await validate_cnpj("123")
    assert result.valid is False
    assert "14 caracteres" in result.error
    mock_api.assert_not_called()


@pytest.mark.asyncio
async def test_validate_cnpj_alfanumerico_formato_valido_chama_api_externa():
    from app.services.cnpj_validator import CnpjResult

    fake_result = CnpjResult(valid=True, cnpj="12ABC34501DE35", company_name="Empresa Teste", status="ATIVA", error="")
    with patch("app.services.cnpj_validator._try_brasilapi", new_callable=AsyncMock, return_value=fake_result) as mock_api:
        result = await validate_cnpj("12.ABC.345/01DE-35")
    mock_api.assert_called_once_with("12ABC34501DE35")
    assert result.valid is True
    assert result.cnpj == "12ABC34501DE35"
