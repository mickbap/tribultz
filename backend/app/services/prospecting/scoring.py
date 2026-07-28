"""Pré-score determinístico (PO-2026-07-SALES-001, Fase 1).

Função pura, sem DB e sem chamada externa: compute_score() recebe os fatos já
consolidados de um escritório e a rubrica carregada, devolve score 0-100, tier e
uma justificativa legível por humano. A checagem de situação cadastral ativa
acontece na consolidação (Fase 3 do trabalho) — um registro inativo nunca chega
a ser pontuado aqui.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.services.prospecting.rubric_loader import Rubric

# Ordem de força dos tiers, do mais alto ao mais baixo — usada pelo cap de MEI.
_TIER_ORDER = ("A", "B", "C", "D")


@dataclass(frozen=True)
class ScoreInput:
    qtd_socios: int
    porte: str  # código RF: "00"|"01"|"03"|"05"
    opcao_mei: bool
    capital_social: Decimal
    data_inicio_atividade: date | None
    email_domain_category: str  # ausente|gratuito|dominio_generico|dominio_nominal
    qtd_estabelecimentos: int
    uf: str
    razao_social: str = ""
    as_of: date = field(default_factory=date.today)


@dataclass(frozen=True)
class ScoreResult:
    score: int
    tier: str
    rubric_version: str
    breakdown: dict[str, int]
    justification: str


def _socios_key(qtd: int) -> str:
    if qtd >= 3:
        return "3_or_more"
    return str(max(qtd, 1))


def _porte_key(porte: str, opcao_mei: bool) -> str:
    # MEI não é um dos 4 códigos de porte da RF (00/01/03/05) — é um flag
    # separado (Simples.csv) que a rubrica trata como uma 5ª chave, com
    # precedência sobre o código de porte declarado.
    if opcao_mei:
        return "mei"
    return porte


def _estabelecimentos_key(qtd: int) -> str:
    if qtd <= 1:
        return "1"
    if qtd <= 3:
        return "2_3"
    return "4_plus"


def _faixa_peso(faixas: list[dict[str, Any]], value: float) -> int:
    for faixa in faixas:
        if "ate" in faixa and value <= faixa["ate"]:
            return int(faixa["peso"])
        if "acima" in faixa and value > faixa["acima"]:
            return int(faixa["peso"])
    return 0


def _idade_anos(data_inicio: date | None, as_of: date) -> float:
    if data_inicio is None:
        return 0.0
    dias = (as_of - data_inicio).days
    return max(dias, 0) / 365.25


def compute_score(inp: ScoreInput, rubric: Rubric) -> ScoreResult:
    breakdown: dict[str, int] = {}

    breakdown["socios"] = rubric.get_weight("socios", _socios_key(inp.qtd_socios))
    breakdown["porte"] = rubric.get_weight("porte", _porte_key(inp.porte, inp.opcao_mei))
    breakdown["capital_social"] = _faixa_peso(
        rubric.scoring["capital_social"]["faixas"], float(inp.capital_social)
    )
    breakdown["idade_anos"] = _faixa_peso(
        rubric.scoring["idade_anos"]["faixas"], _idade_anos(inp.data_inicio_atividade, inp.as_of)
    )
    breakdown["email_domain_category"] = rubric.get_weight(
        "email_domain_category", inp.email_domain_category
    )
    breakdown["estabelecimentos"] = rubric.get_weight(
        "estabelecimentos", _estabelecimentos_key(inp.qtd_estabelecimentos)
    )
    breakdown["geografia"] = rubric.get_weight("geografia", inp.uf)

    raw = rubric.base_score + sum(breakdown.values())
    score = max(0, min(100, raw))
    tier = rubric.tier_for_score(score)

    # Guard de código, não só de rubrica: "nenhum Tier A pode ser MEI" precisa
    # valer mesmo que uma versão futura da rubrica enfraqueça o peso -100 de MEI.
    if inp.opcao_mei and _TIER_ORDER.index(tier) < _TIER_ORDER.index("B"):
        tier = "B"

    justification = _build_justification(inp, breakdown)

    return ScoreResult(
        score=score,
        tier=tier,
        rubric_version=rubric.version,
        breakdown=breakdown,
        justification=justification,
    )


def _build_justification(inp: ScoreInput, breakdown: dict[str, int]) -> str:
    parts: list[str] = []

    if inp.opcao_mei:
        parts.append("MEI")
    elif inp.porte in ("03", "05"):
        parts.append("porte consolidado")

    socios_label = {
        "1": "sócio único", "2": "dois sócios",
    }.get(_socios_key(inp.qtd_socios), "três ou mais sócios")
    parts.append(socios_label)

    if inp.qtd_estabelecimentos > 1:
        parts.append(f"{inp.qtd_estabelecimentos} estabelecimentos (matriz + filiais)")

    domain_label = {
        "dominio_nominal": "domínio de e-mail próprio",
        "dominio_generico": "domínio de e-mail próprio (genérico)",
        "gratuito": "e-mail gratuito",
        "ausente": "sem e-mail cadastrado",
    }[inp.email_domain_category]
    parts.append(domain_label)

    idade = _idade_anos(inp.data_inicio_atividade, inp.as_of)
    if idade >= 10:
        parts.append("empresa consolidada (10+ anos)")
    elif idade < 1:
        parts.append("empresa recém-aberta")

    sentence = ", ".join(parts)
    return sentence[0].upper() + sentence[1:] + "."
