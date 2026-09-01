"""Resolução temporal da eleição IBS/CBS no Simples Nacional.

Implementa as janelas transitórias informadas pelo Jurídico no ROUND FISCAL
01/09-A. O resolvedor é deliberadamente pequeno e opera sobre os fatos
persistidos; não cria um motor temporal genérico.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any, Iterable
from uuid import UUID

from app.models.eleicao_ibs_cbs import ManifestacaoEleicaoIBSCBS


class TipoManifestacao(StrEnum):
    OPCAO_REGIME_REGULAR = "OPCAO_REGIME_REGULAR"
    RENUNCIA_REGIME_REGULAR = "RENUNCIA_REGIME_REGULAR"


class ModalidadeIBSCBS(StrEnum):
    SIMPLES_COM_IBS_CBS_NO_REGIME_UNICO = "SIMPLES_COM_IBS_CBS_NO_REGIME_UNICO"
    SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR = "SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR"
    NAO_DETERMINADA_PELA_EVIDENCIA_DISPONIVEL = (
        "NAO_DETERMINADA_PELA_EVIDENCIA_DISPONIVEL"
    )


class EleicaoIBSCBS(StrEnum):
    COMPROVADA = "COMPROVADA"
    AUSENCIA_DE_OPCAO_COMPROVADA = "AUSENCIA_DE_OPCAO_COMPROVADA"
    NAO_COMPROVADA = "NAO_COMPROVADA"


class CoberturaEvidencia(StrEnum):
    COMPLETA = "COMPLETA"
    INSUFICIENTE = "INSUFICIENTE"


@dataclass(frozen=True)
class JanelaOpcao:
    inicio: date
    fim: date
    eficacia_inicio: date
    eficacia_fim: date
    cancelamento_limite: date


JANELAS_OPCAO = (
    JanelaOpcao(
        inicio=date(2026, 9, 1),
        fim=date(2026, 9, 30),
        eficacia_inicio=date(2027, 1, 1),
        eficacia_fim=date(2027, 6, 30),
        cancelamento_limite=date(2026, 11, 30),
    ),
    JanelaOpcao(
        inicio=date(2027, 3, 1),
        fim=date(2027, 3, 31),
        eficacia_inicio=date(2027, 7, 1),
        eficacia_fim=date(2027, 12, 31),
        cancelamento_limite=date(2027, 5, 31),
    ),
)


@dataclass(frozen=True)
class ResultadoEleicaoIBSCBS:
    eleicao: EleicaoIBSCBS
    modalidade_vigente: ModalidadeIBSCBS
    consultada_em: date
    opcao_apresentada: bool
    opcao_eficaz: bool
    cancelamento_valido: bool
    continuidade_regular: bool
    manifestacao_aplicavel: ManifestacaoEleicaoIBSCBS | None = None


def _texto_obrigatorio(valor: str, campo: str) -> str:
    normalizado = valor.strip()
    if not normalizado:
        raise ValueError(f"{campo} é obrigatório")
    return normalizado


def _janela_da_manifestacao(manifestada_em: date) -> JanelaOpcao | None:
    return next(
        (janela for janela in JANELAS_OPCAO if janela.inicio <= manifestada_em <= janela.fim),
        None,
    )


def criar_opcao_regular(
    *,
    manifestada_em: date,
    fonte: str,
    evidencia_ref: str,
    tenant_id: UUID | None = None,
    cnpj: str | None = None,
) -> ManifestacaoEleicaoIBSCBS:
    """Cria a única manifestação positiva do domínio: opção pelo regular."""
    janela = _janela_da_manifestacao(manifestada_em)
    if janela is None:
        raise ValueError("manifestação fora da janela de opção pelo regime regular")

    atributos: dict[str, Any] = dict(
        tipo_manifestacao=TipoManifestacao.OPCAO_REGIME_REGULAR.value,
        manifestada_em=manifestada_em,
        modalidade=ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR.value,
        eficacia_inicio=janela.eficacia_inicio,
        eficacia_fim=janela.eficacia_fim,
        fonte=_texto_obrigatorio(fonte, "fonte"),
        evidencia_ref=_texto_obrigatorio(evidencia_ref, "evidencia_ref"),
    )
    if tenant_id is not None:
        atributos["tenant_id"] = tenant_id
    if cnpj is not None:
        atributos["cnpj"] = cnpj
    return ManifestacaoEleicaoIBSCBS(**atributos)


def cancelar_opcao_regular(
    opcao: ManifestacaoEleicaoIBSCBS,
    *,
    cancelada_em: date,
    fonte: str,
    evidencia_ref: str,
) -> None:
    """Registra cancelamento tempestivo sem apagar a manifestação histórica."""
    if opcao.tipo_manifestacao != TipoManifestacao.OPCAO_REGIME_REGULAR.value:
        raise ValueError("somente uma opção pelo regime regular pode ser cancelada")
    if opcao.cancelada_em is not None:
        raise ValueError("cancelamento é irretratável e já foi registrado")
    janela = _janela_da_manifestacao(opcao.manifestada_em)
    if janela is None or cancelada_em > janela.cancelamento_limite:
        raise ValueError("cancelamento fora do prazo de cancelamento")
    if cancelada_em < opcao.manifestada_em:
        raise ValueError("cancelamento não pode anteceder a manifestação")

    fonte_normalizada = _texto_obrigatorio(fonte, "fonte do cancelamento")
    evidencia_normalizada = _texto_obrigatorio(
        evidencia_ref, "evidencia_ref do cancelamento"
    )
    opcao.cancelada_em = cancelada_em
    opcao.cancelamento_fonte = fonte_normalizada
    opcao.cancelamento_evidencia_ref = evidencia_normalizada


def _opcao_estruturalmente_valida(registro: ManifestacaoEleicaoIBSCBS) -> bool:
    if registro.tipo_manifestacao != TipoManifestacao.OPCAO_REGIME_REGULAR.value:
        return False
    janela = _janela_da_manifestacao(registro.manifestada_em)
    return bool(
        janela
        and registro.modalidade
        == ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR.value
        and registro.eficacia_inicio == janela.eficacia_inicio
        and registro.eficacia_fim == janela.eficacia_fim
    )


def _cancelamento_valido(
    registro: ManifestacaoEleicaoIBSCBS, consultada_em: date
) -> bool:
    if registro.cancelada_em is None or registro.cancelada_em > consultada_em:
        return False
    janela = _janela_da_manifestacao(registro.manifestada_em)
    return bool(
        janela
        and registro.manifestada_em <= registro.cancelada_em <= janela.cancelamento_limite
        and registro.cancelamento_fonte
        and registro.cancelamento_evidencia_ref
    )


def _renuncia_eficaz(
    registros: list[ManifestacaoEleicaoIBSCBS], consultada_em: date
) -> ManifestacaoEleicaoIBSCBS | None:
    renuncias = [
        registro
        for registro in registros
        if registro.tipo_manifestacao == TipoManifestacao.RENUNCIA_REGIME_REGULAR.value
        and registro.manifestada_em <= consultada_em
        and registro.eficacia_inicio <= consultada_em <= registro.eficacia_fim
        and registro.cancelada_em is None
    ]
    return max(renuncias, key=lambda registro: registro.manifestada_em, default=None)


def resolver_eleicao_ibs_cbs(
    *,
    simples_nacional: bool,
    consultada_em: date,
    cobertura_evidencia: CoberturaEvidencia,
    manifestacoes: Iterable[ManifestacaoEleicaoIBSCBS],
) -> ResultadoEleicaoIBSCBS:
    """Deriva eleição e modalidade em T sem transformar silêncio em evidência."""
    if not simples_nacional:
        raise ValueError("resolvedor restrito a optantes do Simples Nacional")

    registros = [r for r in manifestacoes if r.manifestada_em <= consultada_em]
    opcoes = [r for r in registros if _opcao_estruturalmente_valida(r)]
    opcoes.sort(key=lambda registro: registro.manifestada_em)
    houve_cancelamento = any(_cancelamento_valido(r, consultada_em) for r in opcoes)

    eficazes = [
        r
        for r in opcoes
        if r.eficacia_inicio <= consultada_em <= r.eficacia_fim
        and not _cancelamento_valido(r, consultada_em)
    ]
    opcao_eficaz = eficazes[-1] if eficazes else None
    renuncia = _renuncia_eficaz(registros, consultada_em)

    if opcao_eficaz is not None and renuncia is None:
        return ResultadoEleicaoIBSCBS(
            eleicao=EleicaoIBSCBS.COMPROVADA,
            modalidade_vigente=ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR,
            consultada_em=consultada_em,
            opcao_apresentada=True,
            opcao_eficaz=True,
            cancelamento_valido=houve_cancelamento,
            continuidade_regular=False,
            manifestacao_aplicavel=opcao_eficaz,
        )

    # Uma opção que foi eficaz continua no regular nos períodos seguintes até
    # existir renúncia válida; não se exige repetição semestral da opção.
    anteriores_eficazes = [
        r
        for r in opcoes
        if r.eficacia_fim < consultada_em and not _cancelamento_valido(r, consultada_em)
    ]
    anterior = anteriores_eficazes[-1] if anteriores_eficazes else None
    if anterior is not None and renuncia is None:
        return ResultadoEleicaoIBSCBS(
            eleicao=EleicaoIBSCBS.COMPROVADA,
            modalidade_vigente=ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR,
            consultada_em=consultada_em,
            opcao_apresentada=True,
            opcao_eficaz=True,
            cancelamento_valido=houve_cancelamento,
            continuidade_regular=True,
            manifestacao_aplicavel=anterior,
        )

    # Uma opção pendente ou cancelada comprova o regime único apenas até o fim
    # do período para o qual foi apresentada. Depois disso, um fato histórico
    # não vira prova da ausência de nova opção em janela posterior.
    opcoes_relevantes = [r for r in opcoes if consultada_em <= r.eficacia_fim]
    if opcoes_relevantes or renuncia is not None:
        return ResultadoEleicaoIBSCBS(
            eleicao=EleicaoIBSCBS.COMPROVADA,
            modalidade_vigente=ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_UNICO,
            consultada_em=consultada_em,
            opcao_apresentada=bool(opcoes),
            opcao_eficaz=False,
            cancelamento_valido=houve_cancelamento,
            continuidade_regular=False,
            manifestacao_aplicavel=renuncia or opcoes_relevantes[-1],
        )

    if cobertura_evidencia == CoberturaEvidencia.INSUFICIENTE:
        return ResultadoEleicaoIBSCBS(
            eleicao=EleicaoIBSCBS.NAO_COMPROVADA,
            modalidade_vigente=ModalidadeIBSCBS.NAO_DETERMINADA_PELA_EVIDENCIA_DISPONIVEL,
            consultada_em=consultada_em,
            opcao_apresentada=False,
            opcao_eficaz=False,
            cancelamento_valido=False,
            continuidade_regular=False,
        )

    return ResultadoEleicaoIBSCBS(
        eleicao=EleicaoIBSCBS.AUSENCIA_DE_OPCAO_COMPROVADA,
        modalidade_vigente=ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_UNICO,
        consultada_em=consultada_em,
        opcao_apresentada=False,
        opcao_eficaz=False,
        cancelamento_valido=False,
        continuidade_regular=False,
    )
