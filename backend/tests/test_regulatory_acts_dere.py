"""Contrato documental da DeRE v1.2.0 — sem inferência de efeito tributário."""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.data import regulatory_acts as ra


DATA = Path(ra.__file__).parent


def test_dere_v120_canoniza_publicacao_ato_e_brutos_oficiais():
    dere = ra.get(ra.DERE_V1_2_0)

    assert dere is not None
    assert dere["versao"] == "1.2.0"
    assert dere["publicado_em"] == "2026-09-05"
    assert dere["classificacao_delta"] == "REFINO_OPERACIONAL"
    assert dere["blocker_canonizacao"] == "ZERO"
    assert dere["ato_aprovacao"]["ato_date"] == "2026-09-02"

    assert hashlib.sha256((DATA / dere["arquivo_bruto"]).read_bytes()).hexdigest() == dere["fingerprint"]
    ato = dere["ato_aprovacao"]
    assert hashlib.sha256((DATA / ato["arquivo_bruto"]).read_bytes()).hexdigest() == ato["fingerprint"]

    assert "cgibs.gov.br" in ra.provenance(ra.DERE_V1_2_0).source_url
    assert "cgibs.gov.br" in ra.approval_provenance(ra.DERE_V1_2_0).source_url


def test_dere_v120_canoniza_somente_o_delta_aprovado():
    dere = ra.get(ra.DERE_V1_2_0)
    assert dere is not None
    claims = {claim["id"]: claim for claim in dere["claims"]}

    assert set(claims) == {
        "DERE_120_PUBLICACAO",
        "DERE_120_ATO_APROVACAO",
        "DERE_120_SERIES_TRANSACIONAIS_INICIAIS",
        "DERE_120_CONTROLE_DEDUCOES",
        "DERE_120_REABERTURA_PERIODOS",
        "DERE_120_IDENTIFICACAO_PARTICIPANTES",
        "DERE_120_FINALIDADES_OFICIAIS",
    }
    assert all(claim["classificacao"] == "FATO_NORMATIVO" for claim in claims.values())
    series = claims["DERE_120_SERIES_TRANSACIONAIS_INICIAIS"]["afirmacao"]
    assert all(codigo in series for codigo in ("D-2000", "D-3000", "D-4000"))
    assert "inicial" in series and "preliminar" in series


def test_dere_v120_preserva_fronteiras_e_dependencia_do_mod():
    dere = ra.get(ra.DERE_V1_2_0)
    assert dere is not None

    assert set(dere["limites_interpretativos"]) == {
        "identificacao != efeito tributario automatico",
        "controle de deducao != deducao automaticamente permitida",
        "reabertura != alteracao irrestrita de competencia",
        "v1.2.0 != estrutura transacional final",
    }
    dependencia = dere["dependencia_explicita"]
    assert dependencia["artefato"] == "MOU/MOD atualizado"
    assert dependencia["status"] == "PENDENTE"
    assert {
        "regras de preenchimento",
        "obrigatoriedade por categoria de pessoa fisica",
        "direito a credito",
        "elegibilidade e valor de cashback",
        "determinacao automatica de destino",
        "novos campos e criticas futuras",
    } == set(dependencia["necessario_para"])
    assert "effective_from" not in dere
    assert "alteracao do enquadramento de pessoa fisica, CNPJ ou nanoempreendedor" in dere["inferencias_nao_implementadas"]
