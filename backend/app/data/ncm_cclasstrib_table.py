"""Mapeamento NCM/NBS → cClassTrib (candidatos) — fonte oficial SVRS pública (#313).

Carrega ncm_cclasstrib.json (extraído dos ~4.628 anexos da consulta pública SVRS,
sem credencial — ver scripts/resync_classtrib.py). Usado por /public/ncm/suggest e
/public-api/classify para retornar CANDIDATOS de cClassTrib (6 díg) + base legal,
como SUGESTÃO a validar — nunca um veredito único quando a NCM admite mais de um
(art. 2 da ORDER A: palpite único confiante é o que gera a Rejeição 1024).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.data.classtrib_table import CLASSTRIB_BY_CODE

_DATA = json.loads((Path(__file__).parent / "ncm_cclasstrib.json").read_text(encoding="utf-8"))
NCM_TO_CANDIDATOS: dict[str, list[dict]] = _DATA.get("by_ncm", {})


def _norm_ncm(ncm: str) -> str:
    """Normaliza para só dígitos (remove pontos/traços/espaços)."""
    return "".join(ch for ch in (ncm or "") if ch.isdigit())


def ncm_candidatos(ncm: str) -> list[dict]:
    """Retorna os candidatos cClassTrib para a NCM/NBS: [{codigo, descricao, base_legal, legislacao}].

    Lista vazia quando não há mapeamento (NCM não classificável automaticamente).
    Cada candidato é enriquecido com a descrição oficial do cClassTrib (classtrib.json).
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


def resolve_cclasstrib(ncm: str) -> tuple[str | None, list[dict], str]:
    """(cClassTrib, candidatos, status) para a NCM — sempre SUGESTÃO a validar.

    - 0 candidatos  → (None, [], "requer_validacao")  # sem mapeamento confiável
    - 1 candidato   → (codigo, [cand], "unico")
    - >1 candidatos → (None, [cands], "multiplos")     # nunca veredito único quando há vários
    """
    cands = ncm_candidatos(ncm)
    if not cands:
        return None, [], "requer_validacao"
    if len(cands) == 1:
        return cands[0]["codigo"], cands, "unico"
    return None, cands, "multiplos"
