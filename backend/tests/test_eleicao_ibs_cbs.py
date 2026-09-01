"""Eleição temporal IBS/CBS dos optantes do Simples Nacional — issue #731."""

from datetime import date

import pytest

from app.models.eleicao_ibs_cbs import ManifestacaoEleicaoIBSCBS
from app.services.eleicao_ibs_cbs import (
    CoberturaEvidencia,
    EleicaoIBSCBS,
    ModalidadeIBSCBS,
    cancelar_opcao_regular,
    criar_opcao_regular,
    resolver_eleicao_ibs_cbs,
)


def _opcao_setembro(dia: date = date(2026, 9, 15)) -> ManifestacaoEleicaoIBSCBS:
    return criar_opcao_regular(
        manifestada_em=dia,
        fonte="Portal do Simples Nacional",
        evidencia_ref="protocolo:set-2026",
    )


def _opcao_marco(dia: date = date(2027, 3, 15)) -> ManifestacaoEleicaoIBSCBS:
    return criar_opcao_regular(
        manifestada_em=dia,
        fonte="Portal do Simples Nacional",
        evidencia_ref="protocolo:mar-2027",
    )


def _resolver(
    em: date,
    manifestacoes: list[ManifestacaoEleicaoIBSCBS] | None = None,
    cobertura: CoberturaEvidencia = CoberturaEvidencia.COMPLETA,
):
    return resolver_eleicao_ibs_cbs(
        simples_nacional=True,
        consultada_em=em,
        cobertura_evidencia=cobertura,
        manifestacoes=manifestacoes or [],
    )


def test_a_ausencia_comprovada_de_opcao_mantem_ibs_cbs_no_simples():
    resultado = _resolver(date(2027, 1, 1))

    assert resultado.eleicao == EleicaoIBSCBS.AUSENCIA_DE_OPCAO_COMPROVADA
    assert resultado.modalidade_vigente == ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_UNICO


def test_b_opcao_valida_em_setembro_produz_efeito_em_01_01_2027():
    opcao = _opcao_setembro()

    resultado = _resolver(date(2027, 1, 1), [opcao])

    assert opcao.eficacia_inicio == date(2027, 1, 1)
    assert opcao.eficacia_fim == date(2027, 6, 30)
    assert resultado.modalidade_vigente == ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR


def test_c_opcao_de_setembro_ainda_nao_produz_efeito_em_31_12_2026():
    resultado = _resolver(date(2026, 12, 31), [_opcao_setembro()])

    assert resultado.eleicao == EleicaoIBSCBS.COMPROVADA
    assert resultado.modalidade_vigente == ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_UNICO


def test_d_cancelamento_valido_preserva_historico_e_impede_efeito_no_primeiro_semestre():
    opcao = _opcao_setembro()
    cancelar_opcao_regular(
        opcao,
        cancelada_em=date(2026, 11, 30),
        fonte="Portal do Simples Nacional",
        evidencia_ref="cancelamento:nov-2026",
    )

    resultado = _resolver(date(2027, 1, 1), [opcao])

    assert opcao.manifestada_em == date(2026, 9, 15)
    assert opcao.cancelada_em == date(2026, 11, 30)
    assert resultado.eleicao == EleicaoIBSCBS.COMPROVADA
    assert resultado.cancelamento_valido is True
    assert resultado.modalidade_vigente == ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_UNICO


def test_e_opcao_valida_em_marco_produz_efeito_em_01_07_2027():
    opcao = _opcao_marco()

    antes = _resolver(date(2027, 6, 30), [opcao])
    inicio = _resolver(date(2027, 7, 1), [opcao])

    assert opcao.eficacia_inicio == date(2027, 7, 1)
    assert opcao.eficacia_fim == date(2027, 12, 31)
    assert antes.modalidade_vigente == ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_UNICO
    assert inicio.modalidade_vigente == ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR


def test_f_regular_no_primeiro_semestre_continua_no_segundo_sem_nova_opcao():
    resultado = _resolver(date(2027, 7, 1), [_opcao_setembro()])

    assert resultado.continuidade_regular is True
    assert resultado.modalidade_vigente == ModalidadeIBSCBS.SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR


def test_g_sem_evidencia_suficiente_nunca_presume_regime_unico():
    resultado = _resolver(
        date(2027, 1, 1),
        cobertura=CoberturaEvidencia.INSUFICIENTE,
    )

    assert resultado.eleicao == EleicaoIBSCBS.NAO_COMPROVADA
    assert resultado.modalidade_vigente == ModalidadeIBSCBS.NAO_DETERMINADA_PELA_EVIDENCIA_DISPONIVEL


@pytest.mark.parametrize("dia", [date(2026, 9, 1), date(2026, 9, 30)])
def test_h_limites_inclusivos_da_janela_de_setembro(dia: date):
    assert _opcao_setembro(dia).eficacia_inicio == date(2027, 1, 1)


@pytest.mark.parametrize("dia", [date(2026, 8, 31), date(2026, 10, 1)])
def test_h_fora_da_janela_de_setembro_e_rejeitado(dia: date):
    with pytest.raises(ValueError, match="fora da janela"):
        _opcao_setembro(dia)


@pytest.mark.parametrize("dia", [date(2027, 3, 1), date(2027, 3, 31)])
def test_h_limites_inclusivos_da_janela_de_marco(dia: date):
    assert _opcao_marco(dia).eficacia_inicio == date(2027, 7, 1)


@pytest.mark.parametrize("dia", [date(2027, 2, 28), date(2027, 4, 1)])
def test_h_fora_da_janela_de_marco_e_rejeitado(dia: date):
    with pytest.raises(ValueError, match="fora da janela"):
        _opcao_marco(dia)


@pytest.mark.parametrize(
    ("opcao", "limite"),
    [(_opcao_setembro, date(2026, 11, 30)), (_opcao_marco, date(2027, 5, 31))],
)
def test_h_cancelamento_e_aceito_ate_o_limite_inclusivo(opcao, limite: date):
    registro = opcao()

    cancelar_opcao_regular(
        registro,
        cancelada_em=limite,
        fonte="Portal do Simples Nacional",
        evidencia_ref=f"cancelamento:{limite.isoformat()}",
    )

    assert registro.cancelada_em == limite


@pytest.mark.parametrize(
    ("opcao", "apos_limite"),
    [(_opcao_setembro, date(2026, 12, 1)), (_opcao_marco, date(2027, 6, 1))],
)
def test_h_cancelamento_depois_do_limite_e_rejeitado(opcao, apos_limite: date):
    registro = opcao()

    with pytest.raises(ValueError, match="prazo de cancelamento"):
        cancelar_opcao_regular(
            registro,
            cancelada_em=apos_limite,
            fonte="Portal do Simples Nacional",
            evidencia_ref="cancelamento:intempestivo",
        )


def test_cancelamento_e_irretratavel():
    opcao = _opcao_setembro()
    cancelar_opcao_regular(
        opcao,
        cancelada_em=date(2026, 11, 1),
        fonte="Portal do Simples Nacional",
        evidencia_ref="cancelamento:1",
    )

    with pytest.raises(ValueError, match="irretratável"):
        cancelar_opcao_regular(
            opcao,
            cancelada_em=date(2026, 11, 2),
            fonte="Portal do Simples Nacional",
            evidencia_ref="cancelamento:2",
        )


def test_registro_persiste_fatos_temporais_e_evidencias_em_colunas_separadas():
    colunas = ManifestacaoEleicaoIBSCBS.__table__.columns

    assert {
        "tipo_manifestacao",
        "manifestada_em",
        "modalidade",
        "eficacia_inicio",
        "eficacia_fim",
        "cancelada_em",
        "fonte",
        "evidencia_ref",
        "cancelamento_fonte",
        "cancelamento_evidencia_ref",
    } <= set(colunas.keys())


def test_opcao_apresentada_nao_se_confunde_com_opcao_eficaz():
    resultado = _resolver(date(2026, 10, 1), [_opcao_setembro()])

    assert resultado.opcao_apresentada is True
    assert resultado.opcao_eficaz is False


def test_opcao_cancelada_nao_se_confunde_com_opcao_nunca_apresentada():
    opcao = _opcao_setembro()
    cancelar_opcao_regular(
        opcao,
        cancelada_em=date(2026, 11, 30),
        fonte="Portal do Simples Nacional",
        evidencia_ref="cancelamento:historico",
    )

    resultado = _resolver(date(2027, 1, 1), [opcao])

    assert resultado.opcao_apresentada is True
    assert resultado.opcao_eficaz is False
    assert resultado.cancelamento_valido is True


def test_cancelamento_antigo_nao_prova_ausencia_de_nova_opcao_em_periodo_posterior():
    opcao = _opcao_setembro()
    cancelar_opcao_regular(
        opcao,
        cancelada_em=date(2026, 11, 30),
        fonte="Portal do Simples Nacional",
        evidencia_ref="cancelamento:historico",
    )

    resultado = _resolver(
        date(2027, 7, 1),
        [opcao],
        cobertura=CoberturaEvidencia.INSUFICIENTE,
    )

    assert resultado.eleicao == EleicaoIBSCBS.NAO_COMPROVADA
    assert resultado.modalidade_vigente == ModalidadeIBSCBS.NAO_DETERMINADA_PELA_EVIDENCIA_DISPONIVEL


def test_fora_do_simples_fica_fora_do_escopo_do_resolvedor():
    with pytest.raises(ValueError, match="optantes do Simples Nacional"):
        resolver_eleicao_ibs_cbs(
            simples_nacional=False,
            consultada_em=date(2027, 1, 1),
            cobertura_evidencia=CoberturaEvidencia.COMPLETA,
            manifestacoes=[],
        )
