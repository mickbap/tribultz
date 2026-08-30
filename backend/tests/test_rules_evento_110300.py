"""Contrato do Evento 110300 — Vinculação da Transação de Pagamento (#683, PR B).

NT 2026.006 v1.00 §4. Reutiliza domínio, cortes temporais e política de
conflito do PR A — este arquivo prova que reutiliza, não que duplica.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.data import payment_methods as pm
from app.services import rules_yc_split_linkage as yc
from app.services.rules_yc_split_linkage import avaliar_evento, parse_evento_110300

POS_PROD = dt.date(2026, 11, 10)


def evento(tp_autor="1", meio="15", receb="12345678000195", psp="12345678",
           id_tr="TX-1", desc="Vinculação Pagamento", com_gpgto=True) -> str:
    g = (f'<gPgto idTransacao="{id_tr}"><tpMeioPgto>{meio}</tpMeioPgto>'
         f"<CNPJReceb>{receb}</CNPJReceb><CNPJBasePSP>{psp}</CNPJBasePSP></gPgto>"
         if com_gpgto else "")
    return (f'<envEvento><evento><infEvento><detEvento versao="1.00">'
            f"<descEvento>{desc}</descEvento><cOrgaoAutor>43</cOrgaoAutor>"
            f"<tpAutor>{tp_autor}</tpAutor><verAplic>1.0</verAplic>"
            f"<nProt>143260000000001</nProt>{g}</detEvento></infEvento></evento></envEvento>")


def av(xml: str, ambiente=yc.AMBIENTE_PRODUCAO, emissao=POS_PROD):
    return avaliar_evento(parse_evento_110300(xml), emissao=emissao, ambiente=ambiente)


class TestParse:
    def test_evento_ausente(self):
        e = parse_evento_110300("<nfeProc><NFe/></nfeProc>")
        assert e.presente is False and e.transacao is None
        assert avaliar_evento(e, emissao=POS_PROD, ambiente=yc.AMBIENTE_PRODUCAO) == []

    def test_le_o_leiaute_p17_p28(self):
        e = parse_evento_110300(evento())
        assert e.presente is True
        assert (e.desc_evento, e.c_orgao_autor, e.tp_autor, e.ver_aplic) == (
            "Vinculação Pagamento", "43", "1", "1.0")
        assert e.n_prot == "143260000000001"
        assert e.transacao is not None
        assert (e.transacao.id_transacao, e.transacao.tp_meio_pgto) == ("TX-1", "15")
        assert (e.transacao.cnpj_receb, e.transacao.cnpj_base_psp) == ("12345678000195", "12345678")

    def test_outro_evento_nao_e_reconhecido_como_110300(self):
        assert parse_evento_110300(evento(desc="Cancelamento")).presente is False

    def test_evento_nao_tem_nPag(self):
        """No DF-e gPgto é 1-99 com nPag; no evento é 1-1 e nPag não existe."""
        t = parse_evento_110300(evento()).transacao
        assert t is not None and t.n_pag is None

    def test_evento_valido_zero_achado(self):
        assert av(evento()) == []


class TestP2110:
    @pytest.mark.parametrize("tp", ["2", "3", "5", "6", "9"])
    def test_tpautor_diferente_de_1(self, tp):
        a = [x for x in av(evento(tp_autor=tp)) if x.regra == "P21-10"]
        assert len(a) == 1 and a[0].cstat_esperado == 466

    def test_tpautor_1_sem_achado(self):
        assert [x for x in av(evento(tp_autor="1")) if x.regra == "P21-10"] == []

    def test_tpautor_nao_vira_obrigacao_juridica(self):
        a = [x for x in av(evento(tp_autor="5")) if x.regra == "P21-10"][0]
        assert "não é obrigação jurídica" in a.evidencia["semantica"]
        for texto in (a.detalhe, str(a.evidencia)):
            assert "obrigado a" not in texto and "responsável legal" not in texto


class TestP2610:
    @pytest.mark.parametrize("meio", ["15", "17", "18", "20", "23", "24"])
    def test_subset_admitido_sem_achado(self, meio):
        assert [x for x in av(evento(meio=meio)) if x.regra == "P26-10"] == []

    @pytest.mark.parametrize("meio", ["01", "03", "99", "77"])
    def test_fora_do_subset_invalidade_determinada(self, meio):
        a = [x for x in av(evento(meio=meio)) if x.regra == "P26-10"]
        assert len(a) == 1
        assert a[0].evidencia["invalidade"] == "DETERMINADA"

    def test_cstat_undetermined_com_os_dois_lados(self):
        a = [x for x in av(evento(meio="01")) if x.regra == "P26-10"][0]
        assert a.cstat_esperado == yc.CSTAT_UNDETERMINED
        assert a.evidencia["nt_2026_006_v100"] == 1273
        assert a.evidencia["it_2026_001_v101"] == 1003
        assert a.evidencia["conflict_status"] == "UNRESOLVED"

    def test_cstat_nunca_e_1273_nem_1003(self):
        """Contrato explícito enquanto o conflito estiver aberto."""
        assert pm.conflito_cstat()["conflict_status"] == "UNRESOLVED"
        a = [x for x in av(evento(meio="01")) if x.regra == "P26-10"][0]
        assert a.cstat_esperado != 1273
        assert a.cstat_esperado != 1003
        assert a.cstat_esperado not in ("1273", "1003")

    def test_reutiliza_o_dominio_do_pr_a_sem_duplicar(self):
        a = [x for x in av(evento(meio="01")) if x.regra == "P26-10"][0]
        assert set(a.evidencia["subset_admitido"]) == pm.codigos_admitidos_na_vinculacao()


class TestP2710:
    @pytest.mark.parametrize("cnpj", ["", "123", "1234567800019X", "abc"])
    def test_cnpj_receb_malformado(self, cnpj):
        a = [x for x in av(evento(receb=cnpj)) if x.regra == "P27-10"]
        assert len(a) == 1 and a[0].cstat_esperado == 1274

    def test_escopo_da_validacao_declarado_na_evidencia(self):
        a = [x for x in av(evento(receb="123")) if x.regra == "P27-10"][0]
        assert a.evidencia["escopo_validacao"] == "FORMAT_ONLY"
        assert "DV alfanumérico não conferido" in a.evidencia["limite"]

    def test_recebedor_diferente_do_fornecedor_nao_e_erro(self):
        """A NT permite EXPRESSAMENTE recebedor distinto do fornecedor."""
        assert [x for x in av(evento(receb="99887766000155")) if x.regra == "P27-10"] == []

    def test_cnpj_alfanumerico_aceito(self):
        assert [x for x in av(evento(receb="AB345678000195")) if x.regra == "P27-10"] == []


class TestCortesCompartilhados:
    def test_usa_as_mesmas_constantes_do_pr_a(self):
        assert yc.HOMOLOGACAO == dt.date(2026, 10, 5)
        assert yc.PRODUCAO == dt.date(2026, 11, 3)

    @pytest.mark.parametrize("ambiente,data,esperado", [
        (yc.AMBIENTE_HOMOLOGACAO, dt.date(2026, 10, 4), False),
        (yc.AMBIENTE_HOMOLOGACAO, dt.date(2026, 10, 5), True),
        (yc.AMBIENTE_PRODUCAO, dt.date(2026, 11, 2), False),
        (yc.AMBIENTE_PRODUCAO, dt.date(2026, 11, 3), True),
        (None, POS_PROD, False),
        (yc.AMBIENTE_PRODUCAO, None, False),
    ])
    def test_determinancia(self, ambiente, data, esperado):
        a = av(evento(meio="01"), ambiente=ambiente, emissao=data)
        assert a and all(x.determinante_no_ambiente is esperado for x in a)

    def test_antes_do_corte_ainda_analisa(self):
        a = av(evento(meio="01"), emissao=dt.date(2026, 6, 1))
        assert len(a) == 1 and a[0].determinante_no_ambiente is False


class TestInvariantesDoEvento:
    """Contratos ESTRUTURAIS sobre os modelos expostos, não busca em string."""

    def test_evento_nao_expoe_estado_financeiro(self):
        """Registrado != pago != liquidado. Nenhum campo pode afirmar isso."""
        campos = set(yc.EventoVinculacao.__dataclass_fields__) | \
                 set(yc.TransacaoVinculada.__dataclass_fields__) | \
                 set(yc.AchadoYC.__dataclass_fields__)
        for proibido in ("pago", "liquidado", "liquidacao", "valor", "valor_pago",
                         "valor_split", "conta_rateio", "status_pagamento", "quitado"):
            assert proibido not in campos

    def test_modulo_nao_expoe_api_de_pagamento_ou_liquidacao(self):
        for nome in (n for n in dir(yc) if not n.startswith("_")):
            assert not any(p in nome.lower() for p in
                           ("liquid", "pagou", "quitad", "rateio", "split_calc", "conciliac"))

    def test_idtransacao_nao_prova_liquidacao(self):
        """Evento perfeitamente válido não produz nenhuma afirmação sobre
        pagamento — só ausência de achado."""
        e = parse_evento_110300(evento(id_tr="TX-QUITADA-999"))
        assert av(evento(id_tr="TX-QUITADA-999")) == []
        assert not hasattr(e.transacao, "liquidado")

    def test_cnpjbasepsp_presente_nao_gera_afirmacao_sobre_o_psp(self):
        for a in av(evento(psp="00000000", meio="01")):
            assert "PSP" not in a.detalhe

    def test_evento_ausente_nunca_e_achado(self):
        """Evento disponível tecnicamente != obrigatório em produção 2026."""
        for data in (dt.date(2026, 6, 1), POS_PROD, dt.date(2027, 1, 1)):
            for amb in (yc.AMBIENTE_PRODUCAO, yc.AMBIENTE_HOMOLOGACAO, None):
                assert avaliar_evento(parse_evento_110300("<x/>"), emissao=data, ambiente=amb) == []

    def test_sem_transmissao_registro_ou_cancelamento(self):
        for nome in (n for n in dir(yc) if not n.startswith("_")):
            assert not any(p in nome.lower() for p in
                           ("transmit", "enviar", "registrar_evento", "cancelar", "110001", "sefaz"))
