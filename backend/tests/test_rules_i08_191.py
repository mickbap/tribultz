"""Contrato da RV I08-191 (#615) — NT 2026.007 v1.00.

O eixo destes testes é a separação entre as duas perguntas: condições
documentais (A) e aplicabilidade por SVRS (B). Colapsá-las produziria rejeição
em UF onde a regra não vale.
"""
from __future__ import annotations

import ast
import datetime as dt
import pathlib

import pytest

from app.data import cfop_table
from app.services import rules_i08_191 as rv
from app.services.rules_i08_191 import I08191Entrada, avaliar, mensagem

PRODUCAO = dt.date(2026, 11, 3)
ANTES = dt.date(2026, 9, 15)

_NEGADO = sorted(c for c in cfop_table.all_cfops()
                 if cfop_table.ind_exc_ibscbs(c) == "0")[0]
_PERMITIDO = sorted(cfop_table.cfops_permitidos_contribuinte_exclusivo())[0]


def ent(**kw) -> I08191Entrada:
    base = dict(modelo="55", emit_ie=None, cfops=[_NEGADO], emissao=PRODUCAO, autorizador="SVRS")
    base.update(kw)
    return I08191Entrada(**base)  # type: ignore[arg-type]


class TestCondicoesDocumentais:
    def test_modelo_diferente_de_55_nao_dispara(self):
        r = avaliar(ent(modelo="65"))
        assert r.resultado == rv.SEM_ACHADO and r.condicoes_documentais is False

    def test_ie_informada_nao_dispara(self):
        r = avaliar(ent(emit_ie="123456789"))
        assert r.resultado == rv.SEM_ACHADO
        assert "emit/IE informada" in r.motivo

    @pytest.mark.parametrize("ie", [None, "", "   ", "0", "000000000"])
    def test_ie_ausente_ou_zerada_satisfaz_o_gatilho(self, ie):
        assert avaliar(ent(emit_ie=ie)).condicoes_documentais is True

    def test_cfop_permitido_nao_gera_achado(self):
        r = avaliar(ent(cfops=[_PERMITIDO]))
        assert r.resultado == rv.SEM_ACHADO and r.condicoes_documentais is True

    def test_cfop_fora_do_dominio_oficial_nao_e_tratado_como_nao_permitido(self):
        """`None` (desconhecido) != `False` (existe e não é permitido)."""
        assert cfop_table.permitido_contribuinte_exclusivo_ibscbs("9999") is None
        assert avaliar(ent(cfops=["9999"])).resultado == rv.SEM_ACHADO


class TestExcecoesDocumentais:
    def test_excecao_1_devolucao_finNFe_4(self):
        r = avaliar(ent(fin_nfe="4"))
        assert r.resultado == rv.SEM_ACHADO
        assert r.excecao_aplicada == rv.EXCECAO_DEVOLUCAO

    @pytest.mark.parametrize("tp", ["03", "3"])
    def test_excecao_2_tpNFCredito_03(self, tp):
        r = avaliar(ent(tp_nf_credito=tp))
        assert r.resultado == rv.SEM_ACHADO
        assert r.excecao_aplicada == rv.EXCECAO_RETORNO_RECUSA

    @pytest.mark.parametrize("fin", ["1", "2", "3", None])
    def test_outras_finalidades_nao_isentam(self, fin):
        assert avaliar(ent(fin_nfe=fin)).resultado != rv.SEM_ACHADO

    @pytest.mark.parametrize("tp", ["01", "02", "04", None])
    def test_outros_tipos_de_nota_de_credito_nao_isentam(self, tp):
        assert avaliar(ent(tp_nf_credito=tp)).resultado != rv.SEM_ACHADO


class TestAplicabilidadeSVRS:
    def test_com_svrs_comprovada_e_em_producao_e_deterministica(self):
        r = avaliar(ent(autorizador="SVRS", emissao=PRODUCAO))
        assert r.resultado == rv.REJEICAO_159
        assert r.severidade == "FATAL"
        assert r.aplicabilidade == rv.SVRS_COMPROVADA
        assert "159" in mensagem(r)

    @pytest.mark.parametrize("autorizador", [None, "", "SEFAZ-SP", "unknown"])
    def test_sem_svrs_comprovada_nunca_e_fatal(self, autorizador):
        r = avaliar(ent(autorizador=autorizador))
        assert r.resultado == rv.POSSIVEL_REJEICAO_159
        assert r.severidade == "WARNING"
        assert r.severidade != "FATAL"
        assert r.aplicabilidade == rv.SVRS_NAO_DETERMINADA

    def test_mensagem_sem_svrs_comunica_as_duas_coisas(self):
        m = mensagem(avaliar(ent(autorizador=None)))
        assert "condições documentais da RV I08-191" in m
        assert "não permitido pela tabela corrente" in m
        assert "exclusiva da SVRS" in m
        assert "autorizador aplicável não foi determinado" in m

    def test_A_e_B_nao_sao_colapsadas(self):
        """Sem autorizador, A continua verdadeira e o CFOP negado continua
        identificado — o que muda é só a aplicabilidade."""
        r = avaliar(ent(autorizador=None))
        assert r.condicoes_documentais is True
        assert r.cfop_nao_permitido == _NEGADO
        assert r.aplicabilidade == rv.SVRS_NAO_DETERMINADA


class TestVigencia:
    def test_antes_da_producao_nao_e_fatal_mesmo_com_svrs(self):
        """A IT declara caráter informativo até 03/11/2026."""
        r = avaliar(ent(autorizador="SVRS", emissao=ANTES))
        assert r.severidade == "WARNING"
        assert r.produz_rejeicao_na_data is False
        assert "informativo" in r.motivo

    def test_sem_data_de_emissao_nao_assume_vigencia(self):
        assert avaliar(ent(autorizador="SVRS", emissao=None)).severidade == "WARNING"


class TestSemInferenciaIndevida:
    def test_o_modulo_nao_mapeia_uf_para_autorizador(self):
        """Nenhuma tabela cUF→SVRS no CÓDIGO — por hardcode ou não.

        Varre o código com docstrings removidas: a prosa do módulo diz
        explicitamente que NÃO faz esse mapeamento, e um guard ingênuo de
        texto-fonte se pegaria nela em vez de pegar o defeito.
        """
        arvore = ast.parse(pathlib.Path(rv.__file__).read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                corpo = no.body
                if (corpo and isinstance(corpo[0], ast.Expr)
                        and isinstance(corpo[0].value, ast.Constant)
                        and isinstance(corpo[0].value.value, str)):
                    corpo.pop(0)
        codigo = ast.unparse(arvore)
        for termo in ("cUF", "'RS'", "'SP'", "'MG'", "UF_SVRS", "UFS_SVRS", "UF_PARA_AUTORIZADOR"):
            assert termo not in codigo, f"módulo passou a inferir autorizador via {termo}"

    def test_ie_ausente_nao_classifica_o_contribuinte(self):
        """A ausência de IE é condição do gatilho, nunca conclusão de perfil.
        Nada no resultado afirma que o emitente É contribuinte exclusivo."""
        r = avaliar(ent(emit_ie=None, cfops=[_PERMITIDO]))
        assert r.resultado == rv.SEM_ACHADO
        campos = (r.resultado, r.aplicabilidade, r.motivo, str(r.severidade))
        for texto in campos:
            assert "é contribuinte exclusivo" not in texto
            assert "classificado como" not in texto

    def test_nenhum_resultado_afirma_conformidade_global(self):
        proibidos = ("operação correta", "fiscalmente correta", "conforme", "regular")
        for aut in ("SVRS", None):
            m = mensagem(avaliar(ent(autorizador=aut))).lower()
            for p in proibidos:
                assert p not in m
