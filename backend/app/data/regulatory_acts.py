"""Registro de atos regulatórios versionados (#682, extensão).

Onde vivem atos normativos que o motor CITA mas cuja aplicação depende de
enquadramento que o XML não determina. Complementa ``cfop_table`` e
``payment_methods``, que carregam TABELAS; aqui ficam ATOS, com janela de
efeitos própria.

FRONTEIRA CENTRAL
─────────────────
Este módulo guarda a IDENTIDADE e a JANELA de um ato. Ele não classifica
ninguém. Saber que existe dispensa para o nanoempreendedor não é saber que
*este* emitente é nanoempreendedor — e nada aqui tenta descobrir.

Em particular: ``effective_until`` é fato do artefato, não gatilho. Que o Ato
nº 6/2026 deixe de sustentar a dispensa após 31/12/2028 NÃO autoriza concluir
que em 01/01/2029 a PF está obrigada ao CNPJ. Essa conclusão depende da
legislação então vigente, que não está canonizada aqui.
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import pathlib
from typing import Optional

from app.data.provenance import ArtifactProvenance

_ARQUIVO = pathlib.Path(__file__).with_name("regulatory_acts.json")

ATO_CONJUNTO_RFB_CGIBS_6_2026 = "ATO_CONJUNTO_RFB_CGIBS_6_2026"


@functools.lru_cache(maxsize=1)
def _doc() -> dict:
    return json.loads(_ARQUIVO.read_text(encoding="utf-8"))


def get(chave: str) -> Optional[dict]:
    return _doc()["atos"].get(chave)


def provenance(chave: str) -> ArtifactProvenance:
    a = _doc()["atos"][chave]
    return ArtifactProvenance(
        artefato=a["artefato"], versao=a["versao"], fonte=a["fonte"],
        source_url=a["source_url"],
        observado_em=dt.date.fromisoformat(a["observado_em"]),
        fingerprint=a["fingerprint"], notas=a["observacao_documental"],
    )


def janela_de_efeitos(chave: str) -> tuple[dt.date, dt.date, bool]:
    """``(effective_from, effective_until, until_inclusive)``.

    Descritivo. Nenhum consumidor deve LIGAR ou DESLIGAR comportamento a partir
    daqui sem base normativa própria para isso.
    """
    a = _doc()["atos"][chave]
    return (dt.date.fromisoformat(a["effective_from"]),
            dt.date.fromisoformat(a["effective_until"]),
            bool(a["effective_until_inclusive"]))
