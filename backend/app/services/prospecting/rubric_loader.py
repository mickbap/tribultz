"""Carrega e valida a rubrica YAML de pré-score (PO-2026-07-SALES-001, Fase 1).

Cada versão é um arquivo imutável em backend/app/data/prospecting/rubrics/. Uma
recalibração cria um arquivo novo — nunca edita um existente — para que uma lista
antiga possa ser reprocessada com outra rubrica e comparada estatisticamente
(Fase 4, futura) sem ambiguidade sobre qual versão gerou qual resultado.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

RUBRICS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "prospecting" / "rubrics"

_REQUIRED_TOP_KEYS = ("version", "base_score", "tiers", "scoring")
_REQUIRED_SCORING_DIMENSIONS = (
    "socios",
    "porte",
    "capital_social",
    "idade_anos",
    "email_domain_category",
    "estabelecimentos",
    "geografia",
)


class RubricValidationError(ValueError):
    """Rubrica malformada — faltando chave obrigatória ou tier."""


@dataclass(frozen=True)
class Rubric:
    version: str
    checksum: str
    path: Path
    base_score: int
    tiers: dict[str, dict[str, int]]  # {"A": {"min": 80}, ...}
    scoring: dict[str, Any]

    def get_weight(self, dimension: str, key: str) -> int:
        """Peso de uma dimensão discreta (ex.: socios, porte, estabelecimentos).

        Cai em "default" quando a chave não existe explicitamente na rubrica —
        nunca levanta exceção por cobertura incompleta (ex.: UF não listada).
        """
        weights = self.scoring.get(dimension, {})
        if key in weights:
            return int(weights[key])
        if "default" in weights:
            return int(weights["default"])
        return 0

    def tier_for_score(self, score: int) -> str:
        """Maior tier cujo "min" o score atinge. Tiers ordenados do mais alto ao mais baixo."""
        ordered = sorted(self.tiers.items(), key=lambda kv: kv[1]["min"], reverse=True)
        for tier_name, cfg in ordered:
            if score >= cfg["min"]:
                return tier_name
        return ordered[-1][0] if ordered else "D"

    def to_snapshot(self) -> dict[str, Any]:
        """Serializa os pesos completos — gravado em
        prospect_scoring_runs.rubric_snapshot (Ordem Complementar, item 5) para
        reprodutibilidade total, mesmo se o arquivo YAML mudar ou sumir."""
        return {
            "version": self.version,
            "checksum": self.checksum,
            "base_score": self.base_score,
            "tiers": self.tiers,
            "scoring": self.scoring,
        }


def _resolve_path(version: str | None, path: str | Path | None) -> Path:
    if path is not None:
        return Path(path)
    if not version:
        raise RubricValidationError("Informe --rubric-version ou --rubric-path.")
    return RUBRICS_DIR / f"rubric_{version}.yaml"


def _validate(data: dict[str, Any], source: Path) -> None:
    missing_top = [k for k in _REQUIRED_TOP_KEYS if k not in data]
    if missing_top:
        raise RubricValidationError(f"{source}: faltando chave(s) obrigatória(s): {missing_top}")

    tiers = data["tiers"]
    if not tiers or any("min" not in cfg for cfg in tiers.values()):
        raise RubricValidationError(f"{source}: cada tier precisa de um valor 'min'.")

    scoring = data["scoring"]
    missing_dims = [d for d in _REQUIRED_SCORING_DIMENSIONS if d not in scoring]
    if missing_dims:
        raise RubricValidationError(f"{source}: faltando dimensão(ões) de score: {missing_dims}")


def load_rubric(version: str | None = None, path: str | Path | None = None) -> Rubric:
    """Carrega uma rubrica por versão (resolve o path padrão) ou por path explícito.

    path explícito existe para os testes apontarem para fixtures fora do diretório
    oficial de rubricas versionadas.
    """
    resolved = _resolve_path(version, path)
    if not resolved.exists():
        raise RubricValidationError(f"Rubrica não encontrada: {resolved}")

    raw_bytes = resolved.read_bytes()
    checksum = hashlib.sha256(raw_bytes).hexdigest()
    data = yaml.safe_load(raw_bytes)
    if not isinstance(data, dict):
        raise RubricValidationError(f"{resolved}: YAML inválido (esperado um mapeamento no topo).")

    _validate(data, resolved)

    return Rubric(
        version=str(data["version"]),
        checksum=checksum,
        path=resolved,
        base_score=int(data["base_score"]),
        tiers=data["tiers"],
        scoring=data["scoring"],
    )


_SNAPSHOT_PATH = Path("<rubric_snapshot>")  # placeholder — não há arquivo real


def load_rubric_from_snapshot(snapshot: dict[str, Any]) -> Rubric:
    """Reconstrói uma Rubric a partir de prospect_scoring_runs.rubric_snapshot —
    usada para reprocessar uma classificação antiga com a EXATA rubrica usada
    na época, mesmo que o arquivo YAML original tenha sido alterado ou removido
    (Ordem Complementar, item 5/9 — reclassify_from_snapshot.py)."""
    missing = [k for k in ("version", "checksum", "base_score", "tiers", "scoring") if k not in snapshot]
    if missing:
        raise RubricValidationError(f"Snapshot de rubrica incompleto: faltando {missing}")
    return Rubric(
        version=str(snapshot["version"]),
        checksum=str(snapshot["checksum"]),
        path=_SNAPSHOT_PATH,
        base_score=int(snapshot["base_score"]),
        tiers=snapshot["tiers"],
        scoring=snapshot["scoring"],
    )
