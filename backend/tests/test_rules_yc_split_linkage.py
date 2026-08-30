"""Contrato do grupo YC e do domínio de meios de pagamento (#683).

NT 2026.006 v1.00 + IT 2026.001 v1.01. As invariantes do §8 do round estão em
`TestInvariantes` — são o que impede alguém de "simplificar" isto daqui a três
meses e criar um falso positivo nacional.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.data import payment_methods as pm
from app.services import rules_yc_split_linkage as yc
from app.services.rules_yc_split_linkage import avaliar, parse_grupo_yc

POS_PROD = dt.date(2026, 11, 10)
POS_HOMOL = dt.date(2026, 10, 10)
EM_2026_ANTES = dt.date(2026, 6, 1)


def xml_yc(*transacoes: str, com_grupo: bool = True) -> str:
    corpo = "".join(transacoes)
    grupo = f"<gPgtoVinc>{corpo}</gPgtoVinc>" if com_grupo else ""
    return f"<nfeProc><NFe><infNFe><ide><mod>55</mod></ide>{grupo}</infNFe></NFe></nfeProc>"


def gpgto(n_pag="001", id_tr="TX-1", meio="15", receb="12345678000195", psp="12345678") -> str:
    return (f'<gPgto nPag="{n_pag}" idTransacao="{id_tr}">'
            f"<tpMeioPgto>{meio}</tpMeioPgto><CNPJReceb>{receb}</CNPJReceb>"
            f"<CNPJBasePSP>{psp}</CNPJBasePSP></gPgto>")


class TestDominioVersionado:
    def test_tabela_nacional_tem_23_codigos(self):
        assert len(pm.all_codes()) == 23

    def test_subset_da_vinculacao_tem_6(self):
        assert pm.codigos_admitidos_na_vinculacao() == {"15", "17", "18", "20", "23", "24"}

    def test_propriedade_e_por_codigo_nao_lista_avulsa(self):
        admitido, negado = pm.get("15"), pm.get("01")
        assert admitido is not None and negado is not None
        assert admitido["allowed_in_payment_linkage"] is True
        assert negado["allowed_in_payment_linkage"] is False

    def test_23_e_24_admitidos_e_defasagem_preservada(self):
        assert pm.allowed_in_payment_linkage("23") is True
        assert pm.allowed_in_payment_linkage("24") is True
        d = pm.defasagem_documental_subset()
        assert d["status"] == "DEFASAGEM_DOCUMENTAL_PRESERVADA"
        assert sorted(d["codigos"]) == ["23", "24"]

    def test_proveniencia_dos_dois_artefatos(self):
        assert "nfe.fazenda.gov.br" in pm.provenance().source_url
        assert pm.subset_instituido_por().artefato == "IT 2026.001"
        assert pm.subset_instituido_por().versao == "1.01"

    def test_fingerprint_bate_com_o_bruto(self):
        import hashlib
        import json
        import pathlib
        base = pathlib.Path(pm.__file__).parent
        meta = json.loads((base / "payment_methods.json").read_text(encoding="utf-8"))["meta"]
        bruto = base / meta["arquivo_bruto"]
        assert hashlib.sha256(bruto.read_bytes()).hexdigest() == pm.provenance().fingerprint


class TestParsing:
    def test_grupo_ausente(self):
        g = parse_grupo_yc(xml_yc(com_grupo=False))
        assert g.presente is False and g.transacoes == []

    def test_le_os_sete_campos(self):
        g = parse_grupo_yc(xml_yc(gpgto()))
        assert g.presente is True and len(g.transacoes) == 1
        t = g.transacoes[0]
        assert (t.n_pag, t.id_transacao, t.tp_meio_pgto) == ("001", "TX-1", "15")
        assert (t.cnpj_receb, t.cnpj_base_psp) == ("12345678000195", "12345678")

    def test_multiplas_transacoes(self):
        g = parse_grupo_yc(xml_yc(gpgto("001", "TX-1"), gpgto("002", "TX-2"), gpgto("003", "TX-3")))
        assert len(g.transacoes) == 3

    def test_nao_inventa_campos_inexistentes(self):
        """valor_pago, valor_split, liquidado, data_liquidacao, conta_rateio
        não existem no leiaute e não podem existir na dataclass."""
        campos = set(yc.TransacaoVinculada.__dataclass_fields__)
        for proibido in ("valor_pago", "valor_split", "liquidado", "data_liquidacao",
                         "conta_rateio", "valor", "pago", "liquidacao"):
            assert proibido not in campos


class TestYC0310eYC0420:
    def test_npag_duplicado(self):
        a = avaliar(parse_grupo_yc(xml_yc(gpgto("001", "TX-1"), gpgto("001", "TX-2"))),
                    emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
        r = [x for x in a if x.regra == "YC03-10"]
        assert len(r) == 1 and r[0].cstat_esperado == 215
        assert r[0].natureza == yc.NATUREZA_SCHEMA

    def test_idtransacao_duplicado(self):
        a = avaliar(parse_grupo_yc(xml_yc(gpgto("001", "TX-1"), gpgto("002", "TX-1"))),
                    emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
        r = [x for x in a if x.regra == "YC04-20"]
        assert len(r) == 1 and r[0].cstat_esperado == 215

    def test_215_nunca_e_conclusao_tributaria(self):
        a = avaliar(parse_grupo_yc(xml_yc(gpgto("001", "TX-1"), gpgto("001", "TX-2"))),
                    emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
        for x in [y for y in a if y.cstat_esperado == 215]:
            assert x.natureza == yc.NATUREZA_SCHEMA
            assert x.natureza != yc.NATUREZA_CONTEUDO

    def test_sem_duplicidade_sem_achado(self):
        a = avaliar(parse_grupo_yc(xml_yc(gpgto("001", "TX-1"), gpgto("002", "TX-2"))),
                    emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
        assert [x for x in a if x.cstat_esperado == 215] == []


class TestYC0510:
    @pytest.mark.parametrize("meio", ["15", "17", "18", "20", "23", "24"])
    def test_codigos_admitidos_sem_achado(self, meio):
        a = avaliar(parse_grupo_yc(xml_yc(gpgto(meio=meio))), emissao=POS_PROD,
                    ambiente=yc.AMBIENTE_PRODUCAO)
        assert [x for x in a if x.regra == "YC05-10"] == []

    @pytest.mark.parametrize("meio", ["01", "03", "19", "99"])
    def test_valido_na_tabela_mas_fora_do_subset_e_invalido_aqui(self, meio):
        a = [x for x in avaliar(parse_grupo_yc(xml_yc(gpgto(meio=meio))),
                                emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
             if x.regra == "YC05-10"]
        assert len(a) == 1
        assert a[0].evidencia["na_tabela_nacional"] is True
        assert a[0].evidencia["invalidade"] == "DETERMINADA"

    def test_codigo_fora_da_tabela_nacional(self):
        a = [x for x in avaliar(parse_grupo_yc(xml_yc(gpgto(meio="77"))),
                                emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
             if x.regra == "YC05-10"]
        assert len(a) == 1 and a[0].evidencia["na_tabela_nacional"] is False

    def test_cstat_e_UNDETERMINED_e_a_evidencia_carrega_os_dois_lados(self):
        a = [x for x in avaliar(parse_grupo_yc(xml_yc(gpgto(meio="01"))),
                                emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
             if x.regra == "YC05-10"][0]
        assert a.cstat_esperado == yc.CSTAT_UNDETERMINED
        assert a.evidencia["nt_2026_006_v100"] == 1273
        assert a.evidencia["it_2026_001_v101"] == 1003
        assert a.evidencia["conflict_status"] == "UNRESOLVED"

    def test_tribultz_nunca_escolhe_um_dos_dois_cstat(self):
        a = [x for x in avaliar(parse_grupo_yc(xml_yc(gpgto(meio="01"))),
                                emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
             if x.regra == "YC05-10"][0]
        assert a.cstat_esperado not in (1273, 1003, "1273", "1003")


class TestYC0610:
    @pytest.mark.parametrize("cnpj", ["", "123", "1234567800019X", "abc"])
    def test_cnpj_receb_malformado(self, cnpj):
        a = [x for x in avaliar(parse_grupo_yc(xml_yc(gpgto(receb=cnpj))),
                                emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
             if x.regra == "YC06-10"]
        assert len(a) == 1 and a[0].cstat_esperado == 1274

    def test_cnpj_receb_diferente_do_emitente_nao_e_invalido(self):
        """A NT permite EXPRESSAMENTE recebedor distinto do fornecedor."""
        a = [x for x in avaliar(parse_grupo_yc(xml_yc(gpgto(receb="99887766000155"))),
                                emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
             if x.regra == "YC06-10"]
        assert a == []

    def test_cnpj_alfanumerico_e_aceito(self):
        a = [x for x in avaliar(parse_grupo_yc(xml_yc(gpgto(receb="AB345678000195"))),
                                emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
             if x.regra == "YC06-10"]
        assert a == []


class TestCortesTemporais:
    def test_grupo_ausente_em_2026_zero_achado(self):
        """*"Não há exigência de preenchimento ou uso dos campos de split
        payment em 2026 no ambiente de produção"*."""
        for amb in (yc.AMBIENTE_PRODUCAO, yc.AMBIENTE_HOMOLOGACAO, None):
            for data in (EM_2026_ANTES, POS_PROD, None):
                assert avaliar(parse_grupo_yc(xml_yc(com_grupo=False)),
                               emissao=data, ambiente=amb) == []

    @pytest.mark.parametrize("ambiente,data,esperado", [
        (yc.AMBIENTE_HOMOLOGACAO, dt.date(2026, 10, 4), False),
        (yc.AMBIENTE_HOMOLOGACAO, dt.date(2026, 10, 5), True),
        (yc.AMBIENTE_PRODUCAO, dt.date(2026, 11, 2), False),
        (yc.AMBIENTE_PRODUCAO, dt.date(2026, 11, 3), True),
        (yc.AMBIENTE_PRODUCAO, dt.date(2026, 10, 5), False),
        (None, POS_PROD, False),
        (yc.AMBIENTE_PRODUCAO, None, False),
    ])
    def test_determinancia_por_ambiente_e_data(self, ambiente, data, esperado):
        a = avaliar(parse_grupo_yc(xml_yc(gpgto(meio="01"))), emissao=data, ambiente=ambiente)
        assert a and all(x.determinante_no_ambiente is esperado for x in a)

    def test_grupo_informado_antes_do_corte_ainda_e_avaliado(self):
        """Informou, é validado — o corte muda a determinância, não a análise.
        Deixar de avaliar seria perder o achado; tratar como rejeição
        determinística seria falso positivo."""
        a = avaliar(parse_grupo_yc(xml_yc(gpgto(meio="01"))), emissao=EM_2026_ANTES,
                    ambiente=yc.AMBIENTE_PRODUCAO)
        assert len(a) == 1 and a[0].determinante_no_ambiente is False


class TestInvariantes:
    """As nove invariantes do §8, como contrato executável."""

    def test_national_table_valid_nao_e_allowed_in_gpgtovinc(self):
        assert pm.allowed_in_payment_linkage("01") is False
        assert pm.get("01") is not None
        assert pm.all_codes() > pm.codigos_admitidos_na_vinculacao()

    def test_tpag_nao_e_tpmeiopgto(self):
        # Campos distintos, em grupos distintos: a estrutura de YC não tem tPag.
        assert "tPag" not in yc.TransacaoVinculada.__dataclass_fields__
        assert "tp_meio_pgto" in yc.TransacaoVinculada.__dataclass_fields__

    def test_linkage_nao_e_payment_nem_liquidation(self):
        src = __import__("pathlib").Path(yc.__file__).read_text(encoding="utf-8")
        campos = set(yc.TransacaoVinculada.__dataclass_fields__) | set(yc.AchadoYC.__dataclass_fields__)
        for proibido in ("liquidado", "data_liquidacao", "valor_pago", "valor_split", "conta_rateio"):
            assert proibido not in campos
            assert f"self.{proibido}" not in src

    def test_cnpjreceb_nao_e_necessariamente_o_fornecedor(self):
        assert [x for x in avaliar(parse_grupo_yc(xml_yc(gpgto(receb="99887766000155"))),
                                   emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
                if x.regra == "YC06-10"] == []

    def test_payload_actor_nao_e_obrigacao_legal(self):
        """Presença de CNPJBasePSP no payload não gera achado sobre o PSP."""
        a = avaliar(parse_grupo_yc(xml_yc(gpgto(psp="00000000"))),
                    emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
        assert all("PSP" not in x.detalhe for x in a)

    def test_group_optional_nao_significa_nao_validado_quando_presente(self):
        assert avaliar(parse_grupo_yc(xml_yc(com_grupo=False)), emissao=POS_PROD,
                       ambiente=yc.AMBIENTE_PRODUCAO) == []
        assert avaliar(parse_grupo_yc(xml_yc(gpgto(meio="01"))), emissao=POS_PROD,
                       ambiente=yc.AMBIENTE_PRODUCAO) != []

    def test_invalid_tpmeiopgto_nao_e_cstat_determinado(self):
        a = [x for x in avaliar(parse_grupo_yc(xml_yc(gpgto(meio="01"))),
                                emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO)
             if x.regra == "YC05-10"][0]
        assert a.evidencia["invalidade"] == "DETERMINADA"
        assert a.cstat_esperado == yc.CSTAT_UNDETERMINED

    def test_producao_tecnica_2026_nao_e_split_obrigatorio(self):
        """Nada aqui exige o grupo, em nenhuma data ou ambiente."""
        for data in (POS_PROD, dt.date(2027, 1, 1)):
            for amb in (yc.AMBIENTE_PRODUCAO, yc.AMBIENTE_HOMOLOGACAO):
                assert avaliar(parse_grupo_yc(xml_yc(com_grupo=False)),
                               emissao=data, ambiente=amb) == []

    def test_nenhuma_inferencia_tributaria_a_partir_do_meio_de_pagamento(self):
        src = __import__("pathlib").Path(pm.__file__).read_text(encoding="utf-8")
        publicos = [n for n in dir(pm) if not n.startswith("_")]
        for nome in publicos:
            assert not any(p in nome.lower() for p in
                           ("incidencia", "aliquota", "base_calculo", "tributad", "ibs", "cbs", "split"))
        assert "def calcular" not in src
