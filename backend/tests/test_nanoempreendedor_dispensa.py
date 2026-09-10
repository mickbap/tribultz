"""Dispensa do nanoempreendedor — Ato Conjunto RFB/CGIBS n. 6/2026."""

from __future__ import annotations

import datetime as dt

import pytest

from app.routers.validate_xml import validate_xml
from app.services.nanoempreendedor_dispensa import (
    EnquadramentoNanoempreendedor,
    MotivoDispensaNano,
    ObrigacaoDispensada,
    OpcaoRegimeRegular,
    ResultadoDispensaNano,
    StatusDispensaNano,
    StatusEnquadramentoNano,
    StatusOpcaoRegimeRegular,
    resolver_dispensa_nanoempreendedor,
)


def _nano(status: StatusEnquadramentoNano) -> EnquadramentoNanoempreendedor:
    if status is StatusEnquadramentoNano.INDETERMINADO:
        return EnquadramentoNanoempreendedor(status)
    return EnquadramentoNanoempreendedor(
        status,
        fonte="Evidencia oficial de enquadramento",
        evidencia_ref="evidencia://nano/teste",
    )


def _regime(status: StatusOpcaoRegimeRegular) -> OpcaoRegimeRegular:
    if status is StatusOpcaoRegimeRegular.INDETERMINADO:
        return OpcaoRegimeRegular(status)
    return OpcaoRegimeRegular(
        status,
        fonte="Manifestacao oficial IBS/CBS",
        evidencia_ref="evidencia://eleicao/teste",
    )


NANO = _nano(StatusEnquadramentoNano.NANOEMPREENDEDOR_COMPROVADO)
SEM_OPCAO_REGULAR = _regime(
    StatusOpcaoRegimeRegular.AUSENCIA_DE_OPCAO_COMPROVADA
)
COM_OPCAO_REGULAR = _regime(StatusOpcaoRegimeRegular.OPCAO_COMPROVADA)


def _resolver(
    data: dt.date,
    *,
    nano: EnquadramentoNanoempreendedor | None = NANO,
    regime: OpcaoRegimeRegular | None = SEM_OPCAO_REGULAR,
) -> ResultadoDispensaNano:
    return resolver_dispensa_nanoempreendedor(
        data_referencia=data,
        enquadramento=nano,
        regime_regular=regime,
    )


def _nfe_pf(data: str, *, crt: str = "1", cclass: str = "000001") -> str:
    return (
        f'<nfeProc><NFe><infNFe><ide><mod>55</mod><dhEmi>{data}T10:00:00-03:00</dhEmi></ide>'
        f'<emit><CPF>12345678909</CPF><CRT>{crt}</CRT></emit>'
        '<dest><CPF>11122233344</CPF></dest>'
        '<det nItem="1"><prod><NCM>84713012</NCM><vProd>100.00</vProd></prod>'
        f'<imposto><IBSCBS><CST>410</CST><cClassTrib>{cclass}</cClassTrib>'
        '</IBSCBS></imposto></det><total></total></infNFe></NFe></nfeProc>'
    )


def _alerta_cnpj(
    xml: str,
    *,
    enquadramento_nano: EnquadramentoNanoempreendedor | None = None,
    opcao_regime_regular: OpcaoRegimeRegular | None = None,
):
    return [
        item
        for item in validate_xml(
            xml,
            "NFE",
            enquadramento_nano=enquadramento_nano,
            opcao_regime_regular=opcao_regime_regular,
        ).findings
        if item.rule_id == "PF_CONTRIB_CNPJ"
    ]


@pytest.mark.parametrize(
    "data",
    [dt.date(2026, 8, 29), dt.date(2027, 1, 1), dt.date(2028, 12, 31)],
)
def test_dispensa_aplicavel_na_vigencia_com_dois_fatos_comprovados(
    data: dt.date,
) -> None:
    resultado = _resolver(data)
    assert resultado.status is StatusDispensaNano.APLICAVEL
    assert resultado.dispensa_cnpj_dfe is True
    assert set(resultado.obrigacoes_dispensadas) == {
        ObrigacaoDispensada.INSCRICAO_NO_CNPJ,
        ObrigacaoDispensada.EMISSAO_DFE_IBS_CBS,
    }
    assert resultado.ato["fingerprint"]


def test_data_anterior_ao_inicio_do_ato_nao_aplica_dispensa() -> None:
    resultado = _resolver(dt.date(2026, 8, 28))
    assert resultado.status is StatusDispensaNano.NAO_APLICAVEL
    assert resultado.motivo is MotivoDispensaNano.FORA_DA_VIGENCIA_DO_ATO
    assert resultado.obrigacoes_dispensadas == ()


def test_opcao_regular_comprovada_exclui_dispensa() -> None:
    resultado = _resolver(dt.date(2027, 6, 1), regime=COM_OPCAO_REGULAR)
    assert resultado.status is StatusDispensaNano.NAO_APLICAVEL
    assert resultado.motivo is MotivoDispensaNano.OPCAO_REGIME_REGULAR_COMPROVADA
    assert resultado.obrigacoes_dispensadas == ()


@pytest.mark.parametrize(
    ("nano", "regime", "motivo"),
    [
        (
            None,
            SEM_OPCAO_REGULAR,
            MotivoDispensaNano.ENQUADRAMENTO_NANO_INDETERMINADO,
        ),
        (
            NANO,
            None,
            MotivoDispensaNano.OPCAO_REGIME_REGULAR_INDETERMINADA,
        ),
    ],
)
def test_fato_condicionante_ausente_permanece_indeterminado(
    nano: EnquadramentoNanoempreendedor | None,
    regime: OpcaoRegimeRegular | None,
    motivo: MotivoDispensaNano,
) -> None:
    resultado = _resolver(dt.date(2027, 6, 1), nano=nano, regime=regime)
    assert resultado.status is StatusDispensaNano.INDETERMINADO
    assert resultado.motivo is motivo
    assert resultado.dispensa_cnpj_dfe is False
    assert resultado.obrigacoes_dispensadas == ()


def test_nao_nano_comprovado_nao_recebe_dispensa() -> None:
    resultado = _resolver(
        dt.date(2027, 6, 1),
        nano=_nano(StatusEnquadramentoNano.NAO_NANO_COMPROVADO),
    )
    assert resultado.status is StatusDispensaNano.NAO_APLICAVEL
    assert resultado.motivo is MotivoDispensaNano.ENQUADRAMENTO_NAO_NANO


def test_nao_nano_com_regime_indeterminado_permanece_indeterminado() -> None:
    resultado = _resolver(
        dt.date(2027, 6, 1),
        nano=_nano(StatusEnquadramentoNano.NAO_NANO_COMPROVADO),
        regime=None,
    )
    assert resultado.status is StatusDispensaNano.INDETERMINADO
    assert resultado.motivo is MotivoDispensaNano.OPCAO_REGIME_REGULAR_INDETERMINADA


def test_fim_da_vigencia_nao_vira_dispensa_eterna_nem_obrigacao() -> None:
    resultado = _resolver(dt.date(2029, 1, 1))
    assert resultado.status is StatusDispensaNano.NAO_APLICAVEL
    assert resultado.motivo is MotivoDispensaNano.FORA_DA_VIGENCIA_DO_ATO
    assert resultado.obrigacoes_dispensadas == ()
    assert "obrig" not in resultado.to_dict()["motivo"].lower()


def test_enquadramento_determinado_exige_evidencia() -> None:
    with pytest.raises(ValueError, match="exige fonte e evidencia_ref"):
        EnquadramentoNanoempreendedor(
            StatusEnquadramentoNano.NANOEMPREENDEDOR_COMPROVADO
        )


def test_regime_determinado_exige_evidencia() -> None:
    with pytest.raises(ValueError, match="exige fonte e evidencia_ref"):
        OpcaoRegimeRegular(StatusOpcaoRegimeRegular.AUSENCIA_DE_OPCAO_COMPROVADA)


def test_validador_suprime_alerta_somente_com_dispensa_comprovada() -> None:
    assert _alerta_cnpj(
        _nfe_pf("2027-06-01"),
        enquadramento_nano=NANO,
        opcao_regime_regular=SEM_OPCAO_REGULAR,
    ) == []


def test_validador_mantem_alerta_se_regime_regular_foi_escolhido() -> None:
    alerta = _alerta_cnpj(
        _nfe_pf("2027-06-01"),
        enquadramento_nano=NANO,
        opcao_regime_regular=COM_OPCAO_REGULAR,
    )
    assert len(alerta) == 1 and alerta[0].severity == "ALERT"


@pytest.mark.parametrize(
    ("nano", "regime"),
    [
        (None, None),
        (NANO, None),
        (None, SEM_OPCAO_REGULAR),
    ],
)
def test_validador_fail_closed_mantem_alerta_com_contexto_incompleto(
    nano: EnquadramentoNanoempreendedor | None,
    regime: OpcaoRegimeRegular | None,
) -> None:
    alerta = _alerta_cnpj(
        _nfe_pf("2027-06-01"),
        enquadramento_nano=nano,
        opcao_regime_regular=regime,
    )
    assert len(alerta) == 1 and alerta[0].severity == "ALERT"


def test_crt_e_cclasstrib_nao_provam_enquadramento_nem_dispensa() -> None:
    alerta = _alerta_cnpj(_nfe_pf("2027-06-01", crt="4", cclass="410035"))
    assert len(alerta) == 1 and alerta[0].severity == "ALERT"


def test_data_invalida_nao_quebra_resolucao_da_dispensa() -> None:
    resultado = validate_xml(
        _nfe_pf("2027-99-99"),
        "NFE",
        enquadramento_nano=NANO,
        opcao_regime_regular=SEM_OPCAO_REGULAR,
    )
    assert all(item.rule_id != "PF_CONTRIB_CNPJ" for item in resultado.findings)


def test_dispensa_de_emissao_nao_desliga_validacao_field_level() -> None:
    xml_sem_ibscbs = _nfe_pf("2027-06-01").replace(
        "<IBSCBS><CST>410</CST><cClassTrib>000001</cClassTrib></IBSCBS>",
        "",
    )
    resultado = validate_xml(
        xml_sem_ibscbs,
        "NFE",
        enquadramento_nano=NANO,
        opcao_regime_regular=SEM_OPCAO_REGULAR,
    )
    assert all(item.rule_id != "PF_CONTRIB_CNPJ" for item in resultado.findings)
    assert any(item.rule_id == "IBSCBS_MISSING" for item in resultado.findings)
