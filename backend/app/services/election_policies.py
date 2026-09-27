"""Versioned dispatch shared by legacy Simples and explicit documented elections.

Legacy semantics are frozen behind a compatibility adapter. New regimes cannot
select that adapter, and no policy infers approval from elapsed time.
"""

from __future__ import annotations

from typing import Any

SIMPLES_REGIME = "SIMPLES_NACIONAL"
SIMPLES_VERSION = "SIMPLES_2026_V1"
EXPLICIT_MECHANISM = "EXPLICIT_EVENTS_V1"


def resolve_policy(*, regime: str, version: str, mechanism: str, **context: Any) -> Any:
    if mechanism == SIMPLES_VERSION:
        if (regime, version) != (SIMPLES_REGIME, SIMPLES_VERSION):
            raise ValueError("unknown legacy election policy")
        from app.services.eleicao_ibs_cbs import _resolver_simples_v1

        return _resolver_simples_v1(**context)
    if mechanism == EXPLICIT_MECHANISM and regime.strip() and version.strip():
        from app.services.fiscal_foundations import project_explicit_election

        return project_explicit_election(**context)
    raise ValueError("unknown election policy; no fallback")
