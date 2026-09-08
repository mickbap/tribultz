"""Modelo comparativo econômico v1 do Simples Nacional — IBS/CBS.

Este módulo calcula cenários sem decidir modalidade e sem transformar estimativas
econômicas em direitos tributários. Entradas do cliente permanecem não validadas;
somente parâmetros acompanhados de evidência de validação da Tribultz podem carregar
o estado ``PARAMETRO_VALIDADO_TRIBULTZ``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Any, Iterable


_CENT = Decimal("0.01")
_RATE = Decimal("0.00000001")


class ModalidadeComparativa(StrEnum):
    SIMPLES_COM_IBS_CBS_NO_REGIME_UNICO = "SIMPLES_COM_IBS_CBS_NO_REGIME_UNICO"
    SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR = "SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR"


class EstadoParametro(StrEnum):
    NAO_VALIDADO = "NAO_VALIDADO"
    PARAMETRO_VALIDADO_TRIBULTZ = "PARAMETRO_VALIDADO_TRIBULTZ"


class EstadoCreditoB2B(StrEnum):
    QUALITATIVO = "QUALITATIVO"
    ESTIMATIVA_CONDICIONADA = "ESTIMATIVA_CONDICIONADA"
    AUSENTE = "AUSENTE"


class TipoParametroSimples(StrEnum):
    ALIQUOTA_EFETIVA_CBS_SIMPLES = "ALIQUOTA_EFETIVA_CBS_SIMPLES"
    ALIQUOTA_EFETIVA_IBS_SIMPLES = "ALIQUOTA_EFETIVA_IBS_SIMPLES"


class TipoBreakEven(StrEnum):
    BREAK_EVEN_ECONOMICO_DE_CENARIO = "BREAK_EVEN_ECONOMICO_DE_CENARIO"


class NaturezaParametroCenario(StrEnum):
    PARAMETRO_DE_CENARIO_NAO_DEFINITIVO = "PARAMETRO_DE_CENARIO_NAO_DEFINITIVO"


class EventoJuridicoCaixa(StrEnum):
    EVENTO_JURIDICO_APROPRIACAO_EXTINCAO = "EVENTO_JURIDICO_APROPRIACAO_EXTINCAO"


def _non_negative(value: Decimal | None, field: str) -> None:
    if value is not None and (not value.is_finite() or value < 0):
        raise ValueError(f"{field} deve ser finito e não negativo")


def _rate(value: Decimal | None, field: str) -> None:
    _non_negative(value, field)
    if value is not None and value > 1:
        raise ValueError(f"{field} deve ser informado como fração entre 0 e 1")


def _money(value: Decimal | None) -> Decimal | None:
    return value.quantize(_CENT, ROUND_HALF_UP) if value is not None else None


def _decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


@dataclass(frozen=True)
class EvidenciaValidacaoTribultz:
    fonte: str
    referencia: str
    validada_em: date

    def __post_init__(self) -> None:
        if not self.fonte.strip() or not self.referencia.strip():
            raise ValueError("parâmetro validado exige fonte e referência de evidência")

    def to_dict(self) -> dict[str, str]:
        return {
            "fonte": self.fonte,
            "referencia": self.referencia,
            "validada_em": self.validada_em.isoformat(),
        }


@dataclass(frozen=True)
class ParametroAliquotaSimples:
    tipo: TipoParametroSimples
    valor: Decimal | None
    estado: EstadoParametro
    evidencia: EvidenciaValidacaoTribultz | None = None

    def __post_init__(self) -> None:
        _rate(self.valor, self.tipo.value)
        if self.estado == EstadoParametro.PARAMETRO_VALIDADO_TRIBULTZ:
            if self.valor is None or self.evidencia is None:
                raise ValueError("parâmetro validado exige valor e evidência Tribultz")
        elif self.evidencia is not None:
            raise ValueError("evidência de validação não pode acompanhar parâmetro não validado")

    @classmethod
    def informado_pelo_cliente(
        cls,
        tipo: TipoParametroSimples,
        valor: Decimal | None,
    ) -> ParametroAliquotaSimples:
        return cls(tipo=tipo, valor=valor, estado=EstadoParametro.NAO_VALIDADO)

    @classmethod
    def validado_pela_tribultz(
        cls,
        tipo: TipoParametroSimples,
        valor: Decimal,
        evidencia: EvidenciaValidacaoTribultz,
    ) -> ParametroAliquotaSimples:
        return cls(
            tipo=tipo,
            valor=valor,
            estado=EstadoParametro.PARAMETRO_VALIDADO_TRIBULTZ,
            evidencia=evidencia,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "nome": self.tipo.value,
            "valor": _decimal(self.valor),
            "estado": self.estado.value,
            "evidencia": self.evidencia.to_dict() if self.evidencia else None,
        }


@dataclass(frozen=True)
class ParametrosSimples:
    cbs: ParametroAliquotaSimples
    ibs: ParametroAliquotaSimples

    def __post_init__(self) -> None:
        if self.cbs.tipo != TipoParametroSimples.ALIQUOTA_EFETIVA_CBS_SIMPLES:
            raise ValueError("parâmetro CBS do Simples possui tipo incorreto")
        if self.ibs.tipo != TipoParametroSimples.ALIQUOTA_EFETIVA_IBS_SIMPLES:
            raise ValueError("parâmetro IBS do Simples possui tipo incorreto")

    @property
    def total(self) -> Decimal | None:
        if self.cbs.valor is None or self.ibs.valor is None:
            return None
        return (self.cbs.valor + self.ibs.valor).quantize(_RATE, ROUND_HALF_UP)

    @property
    def confiabilidade(self) -> EstadoParametro:
        if (
            self.total is not None
            and self.cbs.estado == EstadoParametro.PARAMETRO_VALIDADO_TRIBULTZ
            and self.ibs.estado == EstadoParametro.PARAMETRO_VALIDADO_TRIBULTZ
        ):
            return EstadoParametro.PARAMETRO_VALIDADO_TRIBULTZ
        return EstadoParametro.NAO_VALIDADO

    def to_dict(self) -> dict[str, object]:
        return {
            self.cbs.tipo.value: self.cbs.to_dict(),
            self.ibs.tipo.value: self.ibs.to_dict(),
            "ALIQUOTA_EFETIVA_IBS_CBS_SIMPLES": {
                "valor": _decimal(self.total),
                "derivacao": "CBS + IBS",
                "confiabilidade": self.confiabilidade.value,
            },
        }


@dataclass(frozen=True)
class CustoFinanceiroHipotetico:
    montante: Decimal
    periodo_dias: int
    taxa_custo_capital_anual: Decimal

    def __post_init__(self) -> None:
        _non_negative(self.montante, "montante financeiro")
        _rate(self.taxa_custo_capital_anual, "taxa de custo de capital")
        if self.periodo_dias < 0:
            raise ValueError("período financeiro deve ser não negativo")

    @property
    def custo(self) -> Decimal:
        return _money(
            self.montante
            * self.taxa_custo_capital_anual
            * Decimal(self.periodo_dias)
            / Decimal(365)
        ) or Decimal("0.00")

    def to_dict(self) -> dict[str, object]:
        return {
            "tipo": "CUSTO_FINANCEIRO_HIPOTETICO_DO_CENARIO",
            "montante_manual": _decimal(self.montante),
            "periodo_dias_manual": self.periodo_dias,
            "taxa_custo_capital_anual_manual": _decimal(self.taxa_custo_capital_anual),
            "custo_estimado": _decimal(self.custo),
            "evento_juridico_referenciado": EventoJuridicoCaixa.EVENTO_JURIDICO_APROPRIACAO_EXTINCAO.value,
            "parametrizacao_automatica_evento_juridico": False,
        }


@dataclass(frozen=True)
class PremissaCreditoProprio:
    informacao_minima_suficiente: bool = False
    aquisicoes_potencialmente_creditaveis: Decimal | None = None
    coeficiente_credito_potencial_estimado: Decimal | None = None

    def __post_init__(self) -> None:
        _non_negative(
            self.aquisicoes_potencialmente_creditaveis,
            "aquisições potencialmente creditáveis",
        )
        _rate(
            self.coeficiente_credito_potencial_estimado,
            "coeficiente de crédito potencial estimado",
        )
        if self.informacao_minima_suficiente and (
            self.aquisicoes_potencialmente_creditaveis is None
            or self.coeficiente_credito_potencial_estimado is None
        ):
            raise ValueError("estimativa condicionada exige aquisições e coeficiente informados")

    @property
    def estado(self) -> EstadoCreditoB2B:
        if self.informacao_minima_suficiente:
            return EstadoCreditoB2B.ESTIMATIVA_CONDICIONADA
        return EstadoCreditoB2B.QUALITATIVO

    @property
    def valor_estimado(self) -> Decimal | None:
        if not self.informacao_minima_suficiente:
            return None
        assert self.aquisicoes_potencialmente_creditaveis is not None
        assert self.coeficiente_credito_potencial_estimado is not None
        return _money(
            self.aquisicoes_potencialmente_creditaveis
            * self.coeficiente_credito_potencial_estimado
        )


@dataclass(frozen=True)
class PremissasModalidade:
    credito_proprio: PremissaCreditoProprio
    custo_incremental_conformidade: Decimal | None = None
    custo_financeiro: CustoFinanceiroHipotetico | None = None

    def __post_init__(self) -> None:
        _non_negative(
            self.custo_incremental_conformidade,
            "custo incremental de conformidade",
        )


@dataclass(frozen=True)
class PremissasCreditoB2B:
    informacao_minima_suficiente: bool = False
    credito_potencial_estimado: Decimal | None = None

    def __post_init__(self) -> None:
        _non_negative(self.credito_potencial_estimado, "crédito B2B potencial estimado")
        if self.informacao_minima_suficiente != (self.credito_potencial_estimado is not None):
            raise ValueError(
                "crédito B2B condicionado exige informação mínima e estimativa; "
                "sem informação suficiente a estimativa deve permanecer ausente"
            )

    def to_dict(self) -> dict[str, object]:
        potencial = (
            EstadoCreditoB2B.ESTIMATIVA_CONDICIONADA
            if self.informacao_minima_suficiente
            else EstadoCreditoB2B.QUALITATIVO
        )
        return {
            "CREDITO_POTENCIAL_ESTIMADO": {
                "estado": potencial.value,
                "valor": _decimal(_money(self.credito_potencial_estimado)),
            },
            "DIREITO_A_CREDITO_CONFIRMADO": {
                "estado": EstadoCreditoB2B.AUSENTE.value,
                "valor": None,
            },
            "CREDITO_APROPRIADO": {
                "estado": EstadoCreditoB2B.AUSENTE.value,
                "valor": None,
            },
        }


@dataclass(frozen=True)
class CenarioComparativo:
    nome: str
    receita_base: Decimal | None
    aliquota_cbs_regime_regular_cenario: Decimal | None
    aliquota_ibs_regime_regular_cenario: Decimal | None
    regime_unico: PremissasModalidade
    regime_regular: PremissasModalidade
    credito_b2b: PremissasCreditoB2B

    def __post_init__(self) -> None:
        if not self.nome.strip():
            raise ValueError("cenário exige nome")
        _non_negative(self.receita_base, "receita base")
        _rate(
            self.aliquota_cbs_regime_regular_cenario,
            "CBS do regime regular no cenário",
        )
        _rate(
            self.aliquota_ibs_regime_regular_cenario,
            "IBS do regime regular no cenário",
        )

    @property
    def aliquota_regular_total(self) -> Decimal | None:
        if (
            self.aliquota_cbs_regime_regular_cenario is None
            or self.aliquota_ibs_regime_regular_cenario is None
        ):
            return None
        return (
            self.aliquota_cbs_regime_regular_cenario
            + self.aliquota_ibs_regime_regular_cenario
        ).quantize(_RATE, ROUND_HALF_UP)


def parametros_simples_informados(
    *,
    cbs: Decimal | None,
    ibs: Decimal | None,
) -> ParametrosSimples:
    """Fronteira de entrada do produto: dado informado nunca nasce validado."""
    return ParametrosSimples(
        cbs=ParametroAliquotaSimples.informado_pelo_cliente(
            TipoParametroSimples.ALIQUOTA_EFETIVA_CBS_SIMPLES,
            cbs,
        ),
        ibs=ParametroAliquotaSimples.informado_pelo_cliente(
            TipoParametroSimples.ALIQUOTA_EFETIVA_IBS_SIMPLES,
            ibs,
        ),
    )


def _resultado_modalidade(
    *,
    modalidade: ModalidadeComparativa,
    receita: Decimal | None,
    aliquota: Decimal | None,
    confiabilidade: EstadoParametro,
    premissas: PremissasModalidade,
) -> dict[str, object]:
    bruto = _money(receita * aliquota) if receita is not None and aliquota is not None else None
    credito = premissas.credito_proprio.valor_estimado
    liquido = _money(bruto - credito) if bruto is not None and credito is not None else None
    custo_conformidade = _money(premissas.custo_incremental_conformidade)
    custo_financeiro = premissas.custo_financeiro.custo if premissas.custo_financeiro else None
    impacto = None
    if liquido is not None and custo_conformidade is not None:
        impacto = _money(liquido + custo_conformidade + (custo_financeiro or Decimal("0")))

    return {
        "modalidade": modalidade.value,
        "CONFIABILIDADE": confiabilidade.value,
        "IBS_CBS_BRUTO_ESTIMADO": _decimal(bruto),
        "CREDITO_PROPRIO_ESTIMADO": {
            "estado": premissas.credito_proprio.estado.value,
            "valor": _decimal(credito),
        },
        "IBS_CBS_LIQUIDO_ESTIMADO": _decimal(liquido),
        "CUSTO_INCREMENTAL_CONFORMIDADE": _decimal(custo_conformidade),
        "CUSTO_FINANCEIRO_HIPOTETICO_DO_CENARIO": (
            premissas.custo_financeiro.to_dict() if premissas.custo_financeiro else None
        ),
        "IMPACTO_ECONOMICO_TOTAL": _decimal(impacto),
    }


def _break_even(
    cenario: CenarioComparativo,
    resultado_unico: dict[str, object],
    resultado_regular: dict[str, object],
) -> dict[str, object]:
    mensagem = (
        "Mantidas as demais premissas, alterações na intensidade de aquisições "
        "potencialmente creditáveis ao redor do ponto podem alterar o resultado "
        "econômico estimado."
    )
    base = {
        "tipo": TipoBreakEven.BREAK_EVEN_ECONOMICO_DE_CENARIO.value,
        "aquisicoes_potencialmente_creditaveis": None,
        "intensidade_sobre_receita": None,
        "mensagem": mensagem,
    }
    credito_unico = cenario.regime_unico.credito_proprio
    credito_regular = cenario.regime_regular.credito_proprio
    if (
        cenario.receita_base is None
        or cenario.receita_base == 0
        or not credito_unico.informacao_minima_suficiente
        or not credito_regular.informacao_minima_suficiente
        or credito_unico.coeficiente_credito_potencial_estimado is None
        or credito_regular.coeficiente_credito_potencial_estimado is None
        or resultado_unico["IBS_CBS_BRUTO_ESTIMADO"] is None
        or resultado_regular["IBS_CBS_BRUTO_ESTIMADO"] is None
        or cenario.regime_unico.custo_incremental_conformidade is None
        or cenario.regime_regular.custo_incremental_conformidade is None
    ):
        return {**base, "estado": "PREMISSAS_INSUFICIENTES"}

    coeficiente_delta = (
        credito_regular.coeficiente_credito_potencial_estimado
        - credito_unico.coeficiente_credito_potencial_estimado
    )
    if coeficiente_delta == 0:
        return {**base, "estado": "SEM_VARIACAO_MARGINAL_DISTINTA"}

    fixo_unico = (
        Decimal(str(resultado_unico["IBS_CBS_BRUTO_ESTIMADO"]))
        + cenario.regime_unico.custo_incremental_conformidade
        + (cenario.regime_unico.custo_financeiro.custo if cenario.regime_unico.custo_financeiro else Decimal("0"))
    )
    fixo_regular = (
        Decimal(str(resultado_regular["IBS_CBS_BRUTO_ESTIMADO"]))
        + cenario.regime_regular.custo_incremental_conformidade
        + (
            cenario.regime_regular.custo_financeiro.custo
            if cenario.regime_regular.custo_financeiro
            else Decimal("0")
        )
    )
    aquisicoes = _money((fixo_regular - fixo_unico) / coeficiente_delta)
    assert aquisicoes is not None
    intensidade = (aquisicoes / cenario.receita_base).quantize(_RATE, ROUND_HALF_UP)
    return {
        **base,
        "estado": "CALCULADO_SOB_PREMISSAS_DO_CENARIO",
        "aquisicoes_potencialmente_creditaveis": _decimal(aquisicoes),
        "intensidade_sobre_receita": _decimal(intensidade),
    }


def comparar_simples_ibs_cbs(
    *,
    parametros: ParametrosSimples,
    cenarios: Iterable[CenarioComparativo],
) -> dict[str, Any]:
    resultados: list[dict[str, object]] = []
    diagnosticos: list[str] = []

    for cenario in cenarios:
        unico = _resultado_modalidade(
            modalidade=ModalidadeComparativa.SIMPLES_COM_IBS_CBS_NO_REGIME_UNICO,
            receita=cenario.receita_base,
            aliquota=parametros.total,
            confiabilidade=parametros.confiabilidade,
            premissas=cenario.regime_unico,
        )
        regular = _resultado_modalidade(
            modalidade=ModalidadeComparativa.SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR,
            receita=cenario.receita_base,
            aliquota=cenario.aliquota_regular_total,
            confiabilidade=EstadoParametro.NAO_VALIDADO,
            premissas=cenario.regime_regular,
        )
        resultados.append(
            {
                "cenario": cenario.nome,
                "CBS_2027_REGIME_REGULAR": {
                    "valor": _decimal(cenario.aliquota_cbs_regime_regular_cenario),
                    "estado": EstadoParametro.NAO_VALIDADO.value,
                    "natureza": NaturezaParametroCenario.PARAMETRO_DE_CENARIO_NAO_DEFINITIVO.value,
                },
                "IBS_REGIME_REGULAR_CENARIO": {
                    "valor": _decimal(cenario.aliquota_ibs_regime_regular_cenario),
                    "estado": EstadoParametro.NAO_VALIDADO.value,
                    "natureza": NaturezaParametroCenario.PARAMETRO_DE_CENARIO_NAO_DEFINITIVO.value,
                },
                "modalidades": [unico, regular],
                "BREAK_EVEN_ECONOMICO_DE_CENARIO": _break_even(cenario, unico, regular),
                "CREDITO_B2B": cenario.credito_b2b.to_dict(),
            }
        )

        if (
            cenario.regime_unico.credito_proprio.aquisicoes_potencialmente_creditaveis is not None
            or cenario.regime_regular.credito_proprio.aquisicoes_potencialmente_creditaveis is not None
        ):
            diagnosticos.append(
                "Maior intensidade de aquisições potencialmente creditáveis aumenta o peso "
                "econômico da não cumulatividade no cenário."
            )
        if (
            cenario.regime_unico.custo_incremental_conformidade
            != cenario.regime_regular.custo_incremental_conformidade
        ):
            diagnosticos.append(
                "O custo incremental de conformidade altera o peso econômico relativo das "
                "premissas do cenário."
            )
        if cenario.regime_unico.custo_financeiro or cenario.regime_regular.custo_financeiro:
            diagnosticos.append(
                "O componente financeiro reflete somente montante, período e custo de capital "
                "informados manualmente no cenário."
            )

    if not diagnosticos:
        diagnosticos.append(
            "As premissas disponíveis não permitem quantificar o peso econômico de todas as variáveis."
        )

    return {
        "versao_modelo": "SIMPLES_IBS_CBS_COMPARATIVO_V1",
        "PARAMETROS_SIMPLES": parametros.to_dict(),
        "cenarios": resultados,
        "DIAGNOSTICO": list(dict.fromkeys(diagnosticos)),
        "aviso": (
            "Comparação econômica condicionada às premissas informadas; não confirma direito "
            "a crédito e não constitui recomendação automática de modalidade."
        ),
    }
