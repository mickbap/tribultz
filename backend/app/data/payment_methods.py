"""Domínio versionado de meios de pagamento (#683).

DOIS NÍVEIS, NUNCA COLAPSADOS
─────────────────────────────
1. **Tabela Nacional de meios de pagamento** (``tPag``) — 23 códigos, domínio
   geral dos DF-e, publicada no Portal Nacional da NF-e.
2. **Subset admitido no grupo de vinculação** (``tpMeioPgto`` do ``gPgtoVinc``)
   — 6 códigos, instituído pelo **IT 2026.001 v1.01 §1**.

``tPag`` e ``tpMeioPgto`` são campos DIFERENTES em grupos diferentes. Um código
válido na tabela nacional não é, por isso, admitido na vinculação — a
propriedade ``allowed_in_payment_linkage`` é por código, e é ela que responde.
Guardar só os 6 seria transformar o subset em enum eterno, exatamente o que o
catálogo CFOP (#688) existe para não repetir.

O QUE ESTE MÓDULO NÃO SABE, DE PROPÓSITO
─────────────────────────────────────────
Nada sobre pagamento, liquidação, valor, rateio ou tratamento tributário. O
meio de pagamento é um código de identificação da transação; dele não se deriva
incidência, base, alíquota nem obrigação de split. Vínculo não é pagamento;
pagamento não é liquidação.
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import pathlib
from typing import Optional

from app.data.provenance import ArtifactProvenance

_ARQUIVO = pathlib.Path(__file__).with_name("payment_methods.json")


@functools.lru_cache(maxsize=1)
def _doc() -> dict:
    return json.loads(_ARQUIVO.read_text(encoding="utf-8"))


def provenance() -> ArtifactProvenance:
    """Identidade da Tabela Nacional. ``versao=None``: publicada por data."""
    m = _doc()["meta"]
    return ArtifactProvenance(
        artefato=m["artefato"], versao=m["versao"], fonte=m["fonte"],
        source_url=m["source_url"],
        observado_em=dt.date.fromisoformat(m["observado_em"]),
        fingerprint=m["fingerprint"],
    )


def subset_instituido_por() -> ArtifactProvenance:
    """Identidade do IT que institui o subset da vinculação."""
    i = _doc()["meta"]["subset_vinculacao"]["instituido_por"]
    return ArtifactProvenance(
        artefato=i["artefato"], versao=i["versao"],
        fonte="Portal Nacional da NF-e — Informes Técnicos",
        source_url=i["source_url"],
        observado_em=dt.date.fromisoformat(_doc()["meta"]["observado_em"]),
        fingerprint=i["fingerprint"],
    )


def all_codes() -> frozenset[str]:
    """Domínio nacional completo — os 23, não o subset."""
    return frozenset(_doc()["codigos"])


def get(codigo: str) -> Optional[dict]:
    """Registro do código, ou ``None`` se fora da Tabela Nacional."""
    return _doc()["codigos"].get(str(codigo).strip())


def allowed_in_payment_linkage(codigo: str) -> Optional[bool]:
    """Admitido em ``gPgtoVinc``? ``None`` se o código nem existe na tabela.

    ``None`` (fora do domínio nacional) é resposta diferente de ``False``
    (existe na tabela, mas não é admitido na vinculação).
    """
    reg = get(codigo)
    return reg["allowed_in_payment_linkage"] if reg else None


def codigos_admitidos_na_vinculacao() -> frozenset[str]:
    """Subset DERIVADO do domínio. Nunca persistido como lista literal."""
    return frozenset(c for c, v in _doc()["codigos"].items()
                     if v["allowed_in_payment_linkage"])


def conflito_cstat() -> dict:
    """Conflito ABERTO sobre o cStat de ``tpMeioPgto`` inválido.

    NT 2026.006 v1.00 (YC05-10/P26-10) diz **1273**; IT 2026.001 v1.01 §1 diz
    **1003**. A invalidade do código é DETERMINADA; o cStat é UNDETERMINED.
    Escolher um dos dois seria inventar precedência documental.
    """
    return _doc()["meta"]["conflito_cstat_tpmeiopgto"]


def defasagem_documental_subset() -> dict:
    """O IT diz que 23 e 24 "serão atualizados na tabela nacional"; a tabela
    observada já os contém. Defasagem preservada, não bloqueio."""
    return _doc()["meta"]["subset_vinculacao"]["defasagem_documental"]
