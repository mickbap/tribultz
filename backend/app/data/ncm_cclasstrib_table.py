"""Mapeamento NCM/NBS → cClassTrib (candidatos) — fonte oficial SVRS pública (#313).

Carrega ncm_cclasstrib.json (extraído dos ~4.628 anexos da consulta pública SVRS,
sem credencial — ver scripts/resync_classtrib.py).

O que a fonte É — e o que ela não é
------------------------------------
Os anexos catalogam **tratamentos específicos condicionados** (reduções, alíquota
zero, diferimento), não o espaço completo de tratamentos de uma NCM. Duas
verificações sobre o artefato embarcado sustentam isso:

1. ``000001`` (tributação integral) não aparece como candidato de **nenhuma** das
   1.982 NCMs mapeadas. A tributação comum simplesmente não é objeto de anexo.
2. Os títulos dos anexos declaram a condição na própria fonte — "INSUMOS
   AGROPECUÁRIOS", "ALIMENTOS **DESTINADOS AO** CONSUMO HUMANO", "DISPOSITIVOS
   **PRÓPRIOS PARA** PESSOAS COM DEFICIÊNCIA". Destinação e finalidade são
   atributos da **operação**, não da NCM.

Consequência direta: uma NCM constar de exatamente um anexo significa que a fonte
delimita **um** tratamento excepcional possível — não que aquele tratamento se
aplique à operação em análise. Candidato único continua sendo candidato.

Restrição arquitetural (Brain, ``legislation-ontologia-cclasstrib``, approved v1):
"A classificação do item não determina universalmente o tratamento tributário";
"delimitar não é determinar"; "dimensão ausente é ausente — não é zero, não é
padrão, e não deve ser inferida".

Por isso ``resolve_cclasstrib`` **nunca** devolve um cClassTrib: devolve os
candidatos que a fonte delimita e o status que descreve a cardinalidade. Quem
determina é o contexto da operação, que estes endpoints não recebem.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.data.classtrib_table import CLASSTRIB_BY_CODE

_DATA = json.loads((Path(__file__).parent / "ncm_cclasstrib.json").read_text(encoding="utf-8"))
NCM_TO_CANDIDATOS: dict[str, list[dict]] = _DATA.get("by_ncm", {})

#: Status de cardinalidade devolvidos por :func:`resolve_cclasstrib`.
#: Nenhum deles afirma determinação — descrevem só o que a fonte delimita.
STATUS_SEM_MAPEAMENTO = "requer_validacao"   # 0 candidatos na fonte
STATUS_CANDIDATO_UNICO = "candidato_unico"   # 1 candidato — delimitado, não determinado
STATUS_MULTIPLOS = "multiplos"               # >1 candidato


def _norm_ncm(ncm: str) -> str:
    """Normaliza para só dígitos (remove pontos/traços/espaços)."""
    return "".join(ch for ch in (ncm or "") if ch.isdigit())


def ncm_candidatos(ncm: str) -> list[dict]:
    """Retorna os candidatos cClassTrib para a NCM/NBS: [{codigo, descricao, base_legal, legislacao}].

    Lista vazia quando não há mapeamento (NCM não classificável automaticamente).
    Cada candidato é enriquecido com a descrição oficial do cClassTrib (classtrib.json).

    A ordem é a da fonte e **não é ranking**: o primeiro elemento não é "o mais
    provável". Selecionar por posição fabrica uma preferência que a fonte não
    expressa.
    """
    raw = _norm_ncm(ncm)
    entradas = NCM_TO_CANDIDATOS.get(raw) or NCM_TO_CANDIDATOS.get(raw.zfill(8)) or []
    out: list[dict] = []
    for e in entradas:
        codigo = e.get("codigo", "")
        desc = (CLASSTRIB_BY_CODE.get(codigo, {}) or {}).get("description", "")
        out.append({
            "codigo": codigo,
            "descricao": desc,
            "base_legal": e.get("base_legal", ""),
            "legislacao": e.get("legislacao", ""),
        })
    return out


def resolve_cclasstrib(ncm: str) -> tuple[None, list[dict], str]:
    """(None, candidatos, status) para a NCM — sempre candidatos, nunca veredito.

    O primeiro elemento é ``None`` **por contrato**, em qualquer cardinalidade:
    determinar o cClassTrib exige o contexto da operação (destinação, finalidade,
    regime, condições normativas), que não está nesta entrada. A NCM delimita o
    espaço; não escolhe dentro dele.

    - 0 candidatos  → (None, [], "requer_validacao")
    - 1 candidato   → (None, [cand], "candidato_unico")
    - >1 candidatos → (None, [cands], "multiplos")
    """
    cands = ncm_candidatos(ncm)
    if not cands:
        return None, [], STATUS_SEM_MAPEAMENTO
    if len(cands) == 1:
        return None, cands, STATUS_CANDIDATO_UNICO
    return None, cands, STATUS_MULTIPLOS
