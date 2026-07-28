"""Guarda de sanidade de volume da ingestão (Ordem Complementar à
PO-2026-07-SALES-001, item 1).

Compara as métricas de uma execução contra limites absolutos e, quando existe
uma execução anterior compatível (mesmo target_cnaes), contra a variação
relativa. Qualquer violação levanta SanityCheckError — nunca um warning
silencioso; quem chama decide o que fazer (ingest_cnpj_dump.py aborta antes de
gravar qualquer linha em prospect_orgs).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

THRESHOLDS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "prospecting" / "sanity_thresholds.yaml"
)

_REQUIRED_KEYS = (
    "min_target_cnae_found",
    "max_target_cnae_found",
    "min_ativas_ratio",
    "max_relative_change_vs_last_run",
    "max_malformed_row_ratio",
)


class SanityCheckError(Exception):
    """Guarda de sanidade violada — a execução deve abortar sem escrever dados."""


@dataclass(frozen=True)
class IngestionMetrics:
    total_estabelecimentos_scanned: int
    total_target_cnae_found: int
    total_ativas: int
    total_consolidated: int


def load_thresholds(path: Optional[Path] = None) -> dict[str, Any]:
    resolved = path or THRESHOLDS_PATH
    if not resolved.exists():
        raise SanityCheckError(f"Arquivo de tolerâncias não encontrado: {resolved}")
    data = yaml.safe_load(resolved.read_bytes())
    if not isinstance(data, dict):
        raise SanityCheckError(f"{resolved}: YAML inválido (esperado mapeamento no topo).")
    missing = [k for k in _REQUIRED_KEYS if k not in data]
    if missing:
        raise SanityCheckError(f"{resolved}: faltando chave(s) obrigatória(s): {missing}")
    return data


def thresholds_checksum(path: Optional[Path] = None) -> str:
    resolved = path or THRESHOLDS_PATH
    return hashlib.sha256(resolved.read_bytes()).hexdigest()


def validate_metrics(
    metrics: IngestionMetrics,
    thresholds: dict[str, Any],
    previous: Optional[IngestionMetrics] = None,
) -> None:
    """Levanta SanityCheckError na primeira violação encontrada."""
    if metrics.total_target_cnae_found == 0:
        raise SanityCheckError(
            "Zero empresas elegíveis encontradas (CNAE-alvo) — layout pode ter mudado."
        )

    if not (
        thresholds["min_target_cnae_found"]
        <= metrics.total_target_cnae_found
        <= thresholds["max_target_cnae_found"]
    ):
        raise SanityCheckError(
            f"Quantidade de CNAE-alvo encontrada ({metrics.total_target_cnae_found}) fora da "
            f"faixa esperada [{thresholds['min_target_cnae_found']}, "
            f"{thresholds['max_target_cnae_found']}]."
        )

    ativas_ratio = metrics.total_ativas / metrics.total_target_cnae_found
    if ativas_ratio < thresholds["min_ativas_ratio"]:
        raise SanityCheckError(
            f"Proporção de empresas ativas ({ativas_ratio:.1%}) abaixo do mínimo esperado "
            f"({thresholds['min_ativas_ratio']:.1%})."
        )

    if previous is not None and previous.total_target_cnae_found > 0:
        rel_change = (
            abs(metrics.total_target_cnae_found - previous.total_target_cnae_found)
            / previous.total_target_cnae_found
        )
        if rel_change > thresholds["max_relative_change_vs_last_run"]:
            raise SanityCheckError(
                f"Variação de {rel_change:.1%} no total de CNAE-alvo encontrado vs. a última "
                f"execução compatível ({previous.total_target_cnae_found} -> "
                f"{metrics.total_target_cnae_found}), acima da tolerância "
                f"({thresholds['max_relative_change_vs_last_run']:.1%})."
            )


def reduction_summary(metrics: IngestionMetrics) -> dict[str, str]:
    """Percentuais de redução em cada etapa, para o relatório de auditoria (item 8)."""

    def pct(num: int, den: int) -> str:
        if den == 0:
            return "n/a"
        return f"{(1 - num / den):.1%}"

    return {
        "scanned_to_target": pct(metrics.total_target_cnae_found, metrics.total_estabelecimentos_scanned),
        "target_to_ativas": pct(metrics.total_ativas, metrics.total_target_cnae_found),
        "ativas_to_consolidated": pct(metrics.total_consolidated, metrics.total_ativas),
    }
