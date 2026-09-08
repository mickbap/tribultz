"""Modelo comparativo v1 do Simples Nacional — IBS/CBS."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import json

import pytest

from app.services.simples_ibs_cbs_comparison import (
    CenarioComparativo,
    CustoFinanceiroHipotetico,
    EstadoParametro,
    EvidenciaValidacaoTribultz,
    ParametroAliquotaSimples,
    ParametrosSimples,
    PremissaCreditoProprio,
    PremissasCreditoB2B,
    PremissasModalidade,
    TipoParametroSimples,
    comparar_simples_ibs_cbs,
    parametros_simples_informados,
)


def _credito(
    aquisicoes: str | None = "200.00",
    coeficiente: str | None = "0.10",
    *,
    suficiente: bool = True,
) -> PremissaCreditoProprio:
    return PremissaCreditoProprio(
        informacao_minima_suficiente=suficiente,
        aquisicoes_potencialmente_creditaveis=(
            Decimal(aquisicoes) if aquisicoes is not None else None
        ),
        coeficiente_credito_potencial_estimado=(
            Decimal(coeficiente) if coeficiente is not None else None
        ),
    )


def _cenario(
    nome: str = "base",
    *,
    cbs_regular: str | None = "0.03",
    ibs_regular: str | None = "0.15",
    aquisicoes: str = "200.00",
    b2b_suficiente: bool = False,
) -> CenarioComparativo:
    return CenarioComparativo(
        nome=nome,
        receita_base=Decimal("1000.00"),
        aliquota_cbs_regime_regular_cenario=(
            Decimal(cbs_regular) if cbs_regular is not None else None
        ),
        aliquota_ibs_regime_regular_cenario=(
            Decimal(ibs_regular) if ibs_regular is not None else None
        ),
        regime_unico=PremissasModalidade(
            credito_proprio=_credito(aquisicoes, "0.02"),
            custo_incremental_conformidade=Decimal("10.00"),
        ),
        regime_regular=PremissasModalidade(
            credito_proprio=_credito(aquisicoes, "0.18"),
            custo_incremental_conformidade=Decimal("30.00"),
            custo_financeiro=CustoFinanceiroHipotetico(
                montante=Decimal("100.00"),
                periodo_dias=30,
                taxa_custo_capital_anual=Decimal("0.12"),
            ),
        ),
        credito_b2b=PremissasCreditoB2B(
            informacao_minima_suficiente=b2b_suficiente,
            credito_potencial_estimado=(
                Decimal("25.00") if b2b_suficiente else None
            ),
        ),
    )


def _informados(cbs: str | None = "0.01", ibs: str | None = "0.02") -> ParametrosSimples:
    return parametros_simples_informados(
        cbs=Decimal(cbs) if cbs is not None else None,
        ibs=Decimal(ibs) if ibs is not None else None,
    )


def _modalidade(resultado: dict, sufixo: str) -> dict:
    return next(
        item
        for item in resultado["cenarios"][0]["modalidades"]
        if item["modalidade"].endswith(sufixo)
    )


def test_ausencia_de_dados_nao_produz_falsa_precisao() -> None:
    cenario = CenarioComparativo(
        nome="sem dados",
        receita_base=None,
        aliquota_cbs_regime_regular_cenario=None,
        aliquota_ibs_regime_regular_cenario=None,
        regime_unico=PremissasModalidade(credito_proprio=_credito(None, None, suficiente=False)),
        regime_regular=PremissasModalidade(credito_proprio=_credito(None, None, suficiente=False)),
        credito_b2b=PremissasCreditoB2B(),
    )

    resultado = comparar_simples_ibs_cbs(
        parametros=_informados(None, None),
        cenarios=[cenario],
    )

    assert resultado["PARAMETROS_SIMPLES"]["ALIQUOTA_EFETIVA_IBS_CBS_SIMPLES"]["valor"] is None
    for modalidade in resultado["cenarios"][0]["modalidades"]:
        assert modalidade["IBS_CBS_BRUTO_ESTIMADO"] is None
        assert modalidade["IBS_CBS_LIQUIDO_ESTIMADO"] is None
        assert modalidade["IMPACTO_ECONOMICO_TOTAL"] is None
    assert resultado["cenarios"][0]["BREAK_EVEN_ECONOMICO_DE_CENARIO"]["estado"] == (
        "PREMISSAS_INSUFICIENTES"
    )


def test_parametro_informado_permanece_nao_validado() -> None:
    parametros = _informados()

    assert parametros.cbs.estado == EstadoParametro.NAO_VALIDADO
    assert parametros.ibs.estado == EstadoParametro.NAO_VALIDADO
    assert parametros.confiabilidade == EstadoParametro.NAO_VALIDADO
    assert parametros.total == Decimal("0.03000000")


def test_parametros_validados_exigem_evidencia_e_propagam_confiabilidade() -> None:
    with pytest.raises(ValueError, match="valor e evidência"):
        ParametroAliquotaSimples(
            tipo=TipoParametroSimples.ALIQUOTA_EFETIVA_CBS_SIMPLES,
            valor=Decimal("0.01"),
            estado=EstadoParametro.PARAMETRO_VALIDADO_TRIBULTZ,
        )

    evidencia = EvidenciaValidacaoTribultz(
        fonte="registro normativo validado",
        referencia="evidencia://parametros-simples/2027",
        validada_em=date(2026, 9, 8),
    )
    parametros = ParametrosSimples(
        cbs=ParametroAliquotaSimples.validado_pela_tribultz(
            TipoParametroSimples.ALIQUOTA_EFETIVA_CBS_SIMPLES,
            Decimal("0.01"),
            evidencia,
        ),
        ibs=ParametroAliquotaSimples.validado_pela_tribultz(
            TipoParametroSimples.ALIQUOTA_EFETIVA_IBS_SIMPLES,
            Decimal("0.02"),
            evidencia,
        ),
    )

    resultado = comparar_simples_ibs_cbs(parametros=parametros, cenarios=[_cenario()])

    derivado = resultado["PARAMETROS_SIMPLES"]["ALIQUOTA_EFETIVA_IBS_CBS_SIMPLES"]
    assert derivado["valor"] == "0.03000000"
    assert derivado["confiabilidade"] == "PARAMETRO_VALIDADO_TRIBULTZ"
    assert _modalidade(resultado, "REGIME_UNICO")["CONFIABILIDADE"] == (
        "PARAMETRO_VALIDADO_TRIBULTZ"
    )


def test_cbs_2027_e_parametro_alteravel_de_cenario_sem_hardcode_oficial() -> None:
    baixo = comparar_simples_ibs_cbs(
        parametros=_informados(),
        cenarios=[_cenario(cbs_regular="0.01")],
    )
    alto = comparar_simples_ibs_cbs(
        parametros=_informados(),
        cenarios=[_cenario(cbs_regular="0.04")],
    )

    assert _modalidade(baixo, "REGIME_REGULAR")["IBS_CBS_BRUTO_ESTIMADO"] == "160.00"
    assert _modalidade(alto, "REGIME_REGULAR")["IBS_CBS_BRUTO_ESTIMADO"] == "190.00"
    assert baixo["cenarios"][0]["CBS_2027_REGIME_REGULAR"]["natureza"] == (
        "PARAMETRO_DE_CENARIO_NAO_DEFINITIVO"
    )
    assert baixo["cenarios"][0]["CBS_2027_REGIME_REGULAR"]["estado"] == "NAO_VALIDADO"


def test_credito_b2b_separa_potencial_direito_e_apropriacao() -> None:
    qualitativo = comparar_simples_ibs_cbs(
        parametros=_informados(),
        cenarios=[_cenario(b2b_suficiente=False)],
    )["cenarios"][0]["CREDITO_B2B"]
    condicionado = comparar_simples_ibs_cbs(
        parametros=_informados(),
        cenarios=[_cenario(b2b_suficiente=True)],
    )["cenarios"][0]["CREDITO_B2B"]

    assert qualitativo["CREDITO_POTENCIAL_ESTIMADO"] == {
        "estado": "QUALITATIVO",
        "valor": None,
    }
    assert condicionado["CREDITO_POTENCIAL_ESTIMADO"] == {
        "estado": "ESTIMATIVA_CONDICIONADA",
        "valor": "25.00",
    }
    assert condicionado["DIREITO_A_CREDITO_CONFIRMADO"]["estado"] == "AUSENTE"
    assert condicionado["CREDITO_APROPRIADO"]["estado"] == "AUSENTE"


def test_break_even_e_apenas_economico_e_nao_recomenda_modalidade() -> None:
    resultado = comparar_simples_ibs_cbs(parametros=_informados(), cenarios=[_cenario()])
    break_even = resultado["cenarios"][0]["BREAK_EVEN_ECONOMICO_DE_CENARIO"]
    serializado = json.dumps(resultado, ensure_ascii=False).upper()

    assert break_even["tipo"] == "BREAK_EVEN_ECONOMICO_DE_CENARIO"
    assert break_even["estado"] == "CALCULADO_SOB_PREMISSAS_DO_CENARIO"
    assert "MANTIDAS AS DEMAIS PREMISSAS" in break_even["mensagem"].upper()
    assert "MELHOR_MODALIDADE" not in serializado
    assert "FAVORECE_UNICO" not in serializado
    assert "FAVORECE_REGULAR" not in serializado


def test_caixa_usa_somente_inputs_manuais_e_referencia_evento_sem_parametriza_lo() -> None:
    resultado = comparar_simples_ibs_cbs(parametros=_informados(), cenarios=[_cenario()])
    financeiro = _modalidade(resultado, "REGIME_REGULAR")[
        "CUSTO_FINANCEIRO_HIPOTETICO_DO_CENARIO"
    ]
    serializado = json.dumps(resultado, ensure_ascii=False).lower()

    assert financeiro["montante_manual"] == "100.00"
    assert financeiro["periodo_dias_manual"] == 30
    assert financeiro["taxa_custo_capital_anual_manual"] == "0.12"
    assert financeiro["evento_juridico_referenciado"] == (
        "EVENTO_JURIDICO_APROPRIACAO_EXTINCAO"
    )
    assert financeiro["parametrizacao_automatica_evento_juridico"] is False
    assert "fornecedor" not in serializado


def test_cenarios_alteram_resultado_sem_classificacao_automatica() -> None:
    resultado = comparar_simples_ibs_cbs(
        parametros=_informados(),
        cenarios=[_cenario("baixo", aquisicoes="100.00"), _cenario("alto", aquisicoes="600.00")],
    )

    impactos = [
        next(
            modalidade
            for modalidade in cenario["modalidades"]
            if modalidade["modalidade"].endswith("REGIME_REGULAR")
        )["IMPACTO_ECONOMICO_TOTAL"]
        for cenario in resultado["cenarios"]
    ]
    assert impactos[0] != impactos[1]
    assert set(resultado) == {
        "versao_modelo",
        "PARAMETROS_SIMPLES",
        "cenarios",
        "DIAGNOSTICO",
        "aviso",
    }
