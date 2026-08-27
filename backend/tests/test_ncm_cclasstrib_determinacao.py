"""Guardas da #672 Fase 2 — NCM delimita candidatos, não determina tratamento.

Restrição arquitetural: Brain, ``legislation-ontologia-cclasstrib`` (approved v1,
SHA 048e2dc624c4970b2310d23010ddbbc1fa99469d) — "a classificação do item não
determina universalmente o tratamento tributário"; "delimitar não é determinar".

Estes testes protegem a PROPRIEDADE sobre o artefato inteiro, não casos isolados:
uma re-sincronização da fonte não pode reintroduzir veredito único por descuido.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.data.ncm_cclasstrib_table import (
    NCM_TO_CANDIDATOS,
    ncm_candidatos,
    resolve_cclasstrib,
)

_BY_NCM = json.loads(
    (Path(__file__).parent.parent / "app" / "data" / "ncm_cclasstrib.json").read_text(
        encoding="utf-8"
    )
)["by_ncm"]

#: cClassTrib de tributação integral. Existe na tabela oficial, mas não é objeto
#: de anexo — anexo cataloga exceção, e tributação comum não é exceção.
TRIBUTACAO_INTEGRAL = "000001"


class TestNenhumVeredito:
    def test_resolve_nunca_devolve_codigo_para_nenhuma_ncm(self):
        """Varredura completa: nenhuma das NCMs mapeadas produz cClassTrib.

        Guarda a invariante contra a cardinalidade — inclusive as de candidato
        único, que eram exatamente as que devolviam veredito.
        """
        vazou = [
            ncm for ncm in NCM_TO_CANDIDATOS if resolve_cclasstrib(ncm)[0] is not None
        ]
        assert vazou == [], (
            f"{len(vazou)} NCM(s) devolveram cClassTrib determinado, "
            f"ex.: {vazou[:5]}"
        )

    def test_ncm_sem_mapeamento_tambem_nao_devolve(self):
        codigo, cands, status = resolve_cclasstrib("84713012")  # notebook
        assert codigo is None and cands == [] and status == "requer_validacao"

    def test_status_descreve_cardinalidade_sem_afirmar_determinacao(self):
        assert resolve_cclasstrib("02011000")[2] == "candidato_unico"  # 1 anexo
        assert resolve_cclasstrib("10019900")[2] == "multiplos"        # 3 anexos
        assert resolve_cclasstrib("84713012")[2] == "requer_validacao"


class TestPremissaDaFonte:
    """O raciocínio da Fase 2 apoia-se em dois fatos sobre o artefato embarcado.

    Se a fonte mudar de natureza, estes testes falham — e devem falhar, para que
    alguém releia a conclusão em vez de herdá-la.
    """

    def test_tributacao_integral_nao_e_candidato_de_nenhuma_ncm(self):
        com = [
            ncm
            for ncm, ents in _BY_NCM.items()
            if any(e.get("codigo") == TRIBUTACAO_INTEGRAL for e in ents)
        ]
        assert com == [], (
            "A fonte passou a listar 000001 como candidato — os anexos deixaram de "
            "ser catálogo exclusivo de exceção. Reavaliar a #672 Fase 2 antes de "
            "ajustar este teste."
        )

    def test_todo_candidato_carrega_base_legal_rastreavel(self):
        sem = [
            (ncm, e.get("codigo"))
            for ncm, ents in _BY_NCM.items()
            for e in ents
            if not (e.get("base_legal") or "").strip()
        ]
        assert sem == [], f"candidatos sem base legal: {sem[:5]}"


class TestOrdemNaoERanking:
    def test_ordem_dos_candidatos_nao_e_usada_como_preferencia(self):
        """A fonte não ordena por probabilidade.

        1001.99.00 tem candidatos em CST distintos — 200 (redução) e 515
        (diferimento). Nenhum critério da fonte elege um; devolver o primeiro
        apresentaria a ordem de extração como juízo dela.
        """
        cands = ncm_candidatos("10019900")
        assert len(cands) == 3
        assert {c["codigo"] for c in cands} == {"200034", "200038", "515001"}
        assert resolve_cclasstrib("10019900")[0] is None


class TestVocabulario:
    def test_status_unico_aposentado(self):
        """'unico' afirmava determinação; 'candidato_unico' descreve cardinalidade."""
        vistos = {resolve_cclasstrib(n)[2] for n in NCM_TO_CANDIDATOS}
        assert "unico" not in vistos
        assert vistos <= {"candidato_unico", "multiplos"}


@pytest.mark.parametrize("ncm", ["02011000", "10019900", "96190000", "84713012"])
def test_contrato_de_retorno_estavel(ncm):
    codigo, cands, status = resolve_cclasstrib(ncm)
    assert codigo is None
    assert isinstance(cands, list) and isinstance(status, str)
    for c in cands:
        assert set(c) == {"codigo", "descricao", "base_legal", "legislacao"}


class TestContratoDaAPIRecusaVeredito:
    """A recusa é de SCHEMA, não de convenção.

    ``cClassTrib`` foi tipado como ``None`` (não ``Optional[str]``) nos dois
    endpoints. Quem tentar reintroduzir determinação — por regressão, merge ou
    "camada de compatibilidade" — colide com o pydantic antes de chegar ao
    cliente. É a guarda que sobrevive a quem não leu esta issue.
    """

    def test_classify_recusa_cclasstrib_preenchido(self):
        import pydantic

        from app.routers.public_api import ClassifyResponse

        with pytest.raises(pydantic.ValidationError):
            ClassifyResponse(
                ncm="02011000", cClassTrib="200003", cst="000", vBC="1",
                vCBS="1", vIBS="1", total_tributos="1", aliquota_efetiva_pct="1",
                xml_snippet="", credits_used=1, credits_remaining=1,
            )

    def test_suggest_recusa_cclasstrib_preenchido(self):
        import pydantic

        from app.routers.ncm_suggest import SuggestResponse

        with pytest.raises(pydantic.ValidationError):
            SuggestResponse(
                ncm="02011000", ncm_descricao="carne", confidence=0.9,
                cClassTrib="200003",
            )

    def test_openapi_declara_cclasstrib_como_null(self):
        """O contrato publicado ao integrador também diz null — não 'string opcional'."""
        from app.main import app

        schemas = app.openapi()["components"]["schemas"]
        assert schemas["ClassifyResponse"]["properties"]["cClassTrib"].get("type") == "null"
        # /classtrib/validate: campo novo publicado, vocabulário antigo ausente
        props = schemas["ValidateClassTribResponse"]["properties"]
        assert "classtrib_candidatos" in props
