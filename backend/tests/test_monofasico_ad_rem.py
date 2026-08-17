"""MONOFASICO_AD_REM — valores do grupo UB84 conferidos, não só a presença (#478).

Follow-up do #404, que entregou só a checagem estrutural: "o subgrupo existe?".
Aqui o conteúdo é conferido — onde a tripla (quantidade, ad rem, valor) existir,
o produto tem de fechar.

Ad rem é **R$ por unidade**, não percentual: `valor = quantidade × ad rem`, sem
dividir por 100. É a armadilha inversa da do #617 (pCBS/pIBSUF são percentuais e
o motor tratava como fração); quem for uniformizar os dois cálculos depois vai
querer acrescentar /100 aqui. `test_ad_rem_nao_divide_por_cem` existe para barrar.

Fora de escopo, declarado: `gMonoDif` usa percentual (pDifIBS/pDifCBS) sobre
valor, não ad rem sobre quantidade — semântica diferente, e a base do percentual
não foi confirmada em fonte verificável.
"""

from __future__ import annotations

from app.routers.validate_xml import validate_xml


def _nfe(
    *,
    q="1000.0000",
    ad_ibs="0.5000",
    v_ibs="500.00",
    ad_cbs="0.2000",
    v_cbs="200.00",
    dhemi="2027-06-15",
    extra="",
) -> str:
    return (
        "<nfeProc><NFe><infNFe><ide><mod>55</mod>"
        f"<dhEmi>{dhemi}T10:00:00-03:00</dhEmi></ide>"
        "<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>"
        '<det nItem="1"><prod><NCM>27101259</NCM><vProd>5000.00</vProd></prod>'
        "<imposto><IBSCBS><CST>620</CST><cClassTrib>620001</cClassTrib>"
        "<gIBSCBSMono>"
        f"<qBCMono>{q}</qBCMono>"
        f"<adRemIBS>{ad_ibs}</adRemIBS><vIBSMono>{v_ibs}</vIBSMono>"
        f"<adRemCBS>{ad_cbs}</adRemCBS><vCBSMono>{v_cbs}</vCBSMono>"
        f"{extra}"
        "</gIBSCBSMono>"
        "</IBSCBS></imposto></det>"
        "</infNFe></NFe></nfeProc>"
    )


def _achados(xml: str) -> list:
    return [f for f in validate_xml(xml, "NFE").findings if f.rule_id == "MONOFASICO_AD_REM"]


def test_valores_corretos_nao_geram_finding():
    # 1000 × 0,5000 = 500,00 (IBS) e 1000 × 0,2000 = 200,00 (CBS)
    assert _achados(_nfe()) == []


def test_ibs_divergente_gera_finding():
    f = _achados(_nfe(v_ibs="450.00"))
    assert any(x.id == "F_MONOFASICO_AD_REM_VIBSMONO" for x in f)
    assert any("500.00" in x.title for x in f)


def test_cbs_divergente_gera_finding():
    f = _achados(_nfe(v_cbs="123.45"))
    assert any(x.id == "F_MONOFASICO_AD_REM_VCBSMONO" for x in f)


def test_ad_rem_nao_divide_por_cem():
    """Guard da armadilha inversa do #617.

    Se alguém "uniformizar" o cálculo com o do grupo ad valorem e acrescentar
    /100, a nota correta (1000 × 0,5 = 500,00) passaria a ser cobrada como
    5,00 e este teste quebra.
    """
    assert _achados(_nfe(q="1000.0000", ad_ibs="0.5000", v_ibs="500.00")) == []
    # E o valor que seria "esperado" sob a fórmula percentual é reprovado:
    f = _achados(_nfe(q="1000.0000", ad_ibs="0.5000", v_ibs="5.00"))
    assert any(x.id == "F_MONOFASICO_AD_REM_VIBSMONO" for x in f)


def test_tolerancia_de_um_centavo():
    assert _achados(_nfe(v_ibs="500.01")) == []
    assert _achados(_nfe(v_ibs="499.99")) == []
    assert _achados(_nfe(v_ibs="500.02")) != []


def test_severidade_segue_a_janela_de_vigencia():
    """WARNING antes de 04/01/2027 (antecipação), FATAL depois."""
    antes = _achados(_nfe(v_ibs="450.00", dhemi="2026-12-01"))
    depois = _achados(_nfe(v_ibs="450.00", dhemi="2027-06-15"))
    assert antes and all(x.severity == "WARNING" for x in antes)
    assert depois and all(x.severity == "FATAL" for x in depois)


def test_subgrupo_de_retencao_tambem_e_conferido():
    extra = (
        "<gMonoReten><qBCMonoReten>200.0000</qBCMonoReten>"
        "<adRemIBSReten>0.3000</adRemIBSReten><vIBSMonoReten>99.00</vIBSMonoReten>"
        "</gMonoReten>"
    )
    f = _achados(_nfe(extra=extra))
    assert any(x.id == "F_MONOFASICO_AD_REM_VIBSMONORETEN" for x in f), (
        "200 × 0,30 = 60,00; declarado 99,00 deveria ser reprovado"
    )


def test_tripla_incompleta_nao_gera_ruido():
    """Sem os três campos não há o que conferir — regra silencia."""
    extra = "<gMonoRet><qBCMonoRet>10.0000</qBCMonoRet></gMonoRet>"
    assert not [x for x in _achados(_nfe(extra=extra)) if "RET" in x.id and "RETEN" not in x.id]


def test_diferimento_fica_fora_de_escopo():
    """gMonoDif usa percentual, não ad rem — não conferido, e não pode dar falso positivo."""
    extra = "<gMonoDif><pDifIBS>50.0000</pDifIBS><vIBSMonoDif>250.00</vIBSMonoDif></gMonoDif>"
    f = _achados(_nfe(extra=extra))
    assert not any("DIF" in x.id for x in f)
