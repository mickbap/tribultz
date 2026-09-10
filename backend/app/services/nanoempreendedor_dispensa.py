"""Dispensa temporaria de CNPJ/DF-e do nanoempreendedor — Ato n. 6/2026.

Este modulo resolve somente a consequencia de fatos ja comprovados. Ele nao
classifica pessoa fisica, nao usa receita, atividade, CRT ou cClassTrib como
proxy de nanoempreendedor e nao transforma o fim da dispensa em obrigacao.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.data import regulatory_acts


class StatusEnquadramentoNano(StrEnum):
    NANOEMPREENDEDOR_COMPROVADO = "NANOEMPREENDEDOR_COMPROVADO"
    NAO_NANO_COMPROVADO = "NAO_NANO_COMPROVADO"
    INDETERMINADO = "INDETERMINADO"


class StatusOpcaoRegimeRegular(StrEnum):
    OPCAO_COMPROVADA = "OPCAO_COMPROVADA"
    AUSENCIA_DE_OPCAO_COMPROVADA = "AUSENCIA_DE_OPCAO_COMPROVADA"
    INDETERMINADO = "INDETERMINADO"


class ObrigacaoDispensada(StrEnum):
    INSCRICAO_NO_CNPJ = "INSCRICAO_NO_CNPJ"
    EMISSAO_DFE_IBS_CBS = "EMISSAO_DFE_IBS_CBS"


class StatusDispensaNano(StrEnum):
    APLICAVEL = "APLICAVEL"
    NAO_APLICAVEL = "NAO_APLICAVEL"
    INDETERMINADO = "INDETERMINADO"


class MotivoDispensaNano(StrEnum):
    DISPENSA_TEMPORARIA_APLICAVEL = "DISPENSA_TEMPORARIA_APLICAVEL"
    FORA_DA_VIGENCIA_DO_ATO = "FORA_DA_VIGENCIA_DO_ATO"
    ENQUADRAMENTO_NANO_INDETERMINADO = "ENQUADRAMENTO_NANO_INDETERMINADO"
    ENQUADRAMENTO_NAO_NANO = "ENQUADRAMENTO_NAO_NANO"
    OPCAO_REGIME_REGULAR_INDETERMINADA = "OPCAO_REGIME_REGULAR_INDETERMINADA"
    OPCAO_REGIME_REGULAR_COMPROVADA = "OPCAO_REGIME_REGULAR_COMPROVADA"


def _validar_evidencia(
    *,
    indeterminado: bool,
    fonte: str | None,
    evidencia_ref: str | None,
) -> None:
    if indeterminado:
        return
    if not fonte or not fonte.strip() or not evidencia_ref or not evidencia_ref.strip():
        raise ValueError("estado determinado exige fonte e evidencia_ref")


@dataclass(frozen=True)
class EnquadramentoNanoempreendedor:
    status: StatusEnquadramentoNano
    fonte: str | None = None
    evidencia_ref: str | None = None

    def __post_init__(self) -> None:
        _validar_evidencia(
            indeterminado=self.status is StatusEnquadramentoNano.INDETERMINADO,
            fonte=self.fonte,
            evidencia_ref=self.evidencia_ref,
        )

    def to_dict(self) -> dict[str, str | None]:
        return {
            "status": self.status.value,
            "fonte": self.fonte,
            "evidencia_ref": self.evidencia_ref,
        }


@dataclass(frozen=True)
class OpcaoRegimeRegular:
    status: StatusOpcaoRegimeRegular
    fonte: str | None = None
    evidencia_ref: str | None = None

    def __post_init__(self) -> None:
        _validar_evidencia(
            indeterminado=self.status is StatusOpcaoRegimeRegular.INDETERMINADO,
            fonte=self.fonte,
            evidencia_ref=self.evidencia_ref,
        )

    def to_dict(self) -> dict[str, str | None]:
        return {
            "status": self.status.value,
            "fonte": self.fonte,
            "evidencia_ref": self.evidencia_ref,
        }


@dataclass(frozen=True)
class ResultadoDispensaNano:
    status: StatusDispensaNano
    motivo: MotivoDispensaNano
    data_referencia: dt.date
    vigencia_inicial: dt.date
    vigencia_final: dt.date
    obrigacoes_dispensadas: tuple[ObrigacaoDispensada, ...]
    enquadramento: EnquadramentoNanoempreendedor
    regime_regular: OpcaoRegimeRegular
    ato: dict[str, Any]

    @property
    def dispensa_cnpj_dfe(self) -> bool:
        return self.status is StatusDispensaNano.APLICAVEL and set(
            self.obrigacoes_dispensadas
        ) == {
            ObrigacaoDispensada.INSCRICAO_NO_CNPJ,
            ObrigacaoDispensada.EMISSAO_DFE_IBS_CBS,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "motivo": self.motivo.value,
            "data_referencia": self.data_referencia.isoformat(),
            "vigencia_inicial": self.vigencia_inicial.isoformat(),
            "vigencia_final": self.vigencia_final.isoformat(),
            "obrigacoes_dispensadas": [item.value for item in self.obrigacoes_dispensadas],
            "enquadramento": self.enquadramento.to_dict(),
            "regime_regular": self.regime_regular.to_dict(),
            "ato": self.ato,
        }


def _resultado(
    *,
    status: StatusDispensaNano,
    motivo: MotivoDispensaNano,
    data_referencia: dt.date,
    vigencia_inicial: dt.date,
    vigencia_final: dt.date,
    enquadramento: EnquadramentoNanoempreendedor,
    regime_regular: OpcaoRegimeRegular,
    dispensadas: bool = False,
) -> ResultadoDispensaNano:
    prov = regulatory_acts.provenance(
        regulatory_acts.ATO_CONJUNTO_RFB_CGIBS_6_2026
    )
    return ResultadoDispensaNano(
        status=status,
        motivo=motivo,
        data_referencia=data_referencia,
        vigencia_inicial=vigencia_inicial,
        vigencia_final=vigencia_final,
        obrigacoes_dispensadas=(
            (
                ObrigacaoDispensada.INSCRICAO_NO_CNPJ,
                ObrigacaoDispensada.EMISSAO_DFE_IBS_CBS,
            )
            if dispensadas
            else ()
        ),
        enquadramento=enquadramento,
        regime_regular=regime_regular,
        ato=prov.to_dict(),
    )


def resolver_dispensa_nanoempreendedor(
    *,
    data_referencia: dt.date,
    enquadramento: EnquadramentoNanoempreendedor | None,
    regime_regular: OpcaoRegimeRegular | None,
) -> ResultadoDispensaNano:
    """Resolve a dispensa sem inferir nenhum dos dois fatos condicionantes."""
    enquadramento_resolvido = enquadramento or EnquadramentoNanoempreendedor(
        StatusEnquadramentoNano.INDETERMINADO
    )
    regime_resolvido = regime_regular or OpcaoRegimeRegular(
        StatusOpcaoRegimeRegular.INDETERMINADO
    )
    inicio, fim, fim_inclusivo = regulatory_acts.janela_de_efeitos(
        regulatory_acts.ATO_CONJUNTO_RFB_CGIBS_6_2026
    )
    if not fim_inclusivo:
        raise ValueError("Ato n. 6/2026 deve possuir vigencia final inclusiva")

    argumentos = {
        "data_referencia": data_referencia,
        "vigencia_inicial": inicio,
        "vigencia_final": fim,
        "enquadramento": enquadramento_resolvido,
        "regime_regular": regime_resolvido,
    }
    if not inicio <= data_referencia <= fim:
        return _resultado(
            status=StatusDispensaNano.NAO_APLICAVEL,
            motivo=MotivoDispensaNano.FORA_DA_VIGENCIA_DO_ATO,
            **argumentos,
        )
    if enquadramento_resolvido.status is StatusEnquadramentoNano.INDETERMINADO:
        return _resultado(
            status=StatusDispensaNano.INDETERMINADO,
            motivo=MotivoDispensaNano.ENQUADRAMENTO_NANO_INDETERMINADO,
            **argumentos,
        )
    if regime_resolvido.status is StatusOpcaoRegimeRegular.INDETERMINADO:
        return _resultado(
            status=StatusDispensaNano.INDETERMINADO,
            motivo=MotivoDispensaNano.OPCAO_REGIME_REGULAR_INDETERMINADA,
            **argumentos,
        )
    if enquadramento_resolvido.status is StatusEnquadramentoNano.NAO_NANO_COMPROVADO:
        return _resultado(
            status=StatusDispensaNano.NAO_APLICAVEL,
            motivo=MotivoDispensaNano.ENQUADRAMENTO_NAO_NANO,
            **argumentos,
        )
    if regime_resolvido.status is StatusOpcaoRegimeRegular.OPCAO_COMPROVADA:
        return _resultado(
            status=StatusDispensaNano.NAO_APLICAVEL,
            motivo=MotivoDispensaNano.OPCAO_REGIME_REGULAR_COMPROVADA,
            **argumentos,
        )
    return _resultado(
        status=StatusDispensaNano.APLICAVEL,
        motivo=MotivoDispensaNano.DISPENSA_TEMPORARIA_APLICAVEL,
        dispensadas=True,
        **argumentos,
    )
