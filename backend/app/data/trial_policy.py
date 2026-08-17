"""Política do Trial — fonte única de verdade (#635, L1.5).

Carrega `trial_policy.json`, que é a decisão de Produto de 16/08/2026 em forma
legível por máquina. Backend e superfícies públicas derivam daqui; nada de
número solto em copy ou em regra.

O ponto que motivou a issue: havia três verdades simultâneas — "Grátis por 3
dias · 5 validações" no /register, "5 validações XML **por mês**" no /pricing e
"5 validações grátis" (sem prazo) na home. Qual delas era o contrato não estava
decidido em lugar nenhum.

`quota_period = trial_lifetime` é a parte com consequência de código, não de
copy: `check_usage_limit` contava por mês-calendário, então um trial ativado no
dia 30 ganhava franquia nova no dia 1º e chegava a 10 validações em 3 dias.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_POLICY: dict[str, Any] = json.loads(
    (Path(__file__).parent / "trial_policy.json").read_text(encoding="utf-8")
)

TRIAL_DURATION_DAYS: int = int(_POLICY["duration_days"])
TRIAL_VALIDATION_QUOTA: int = int(_POLICY["validation_quota"])
TRIAL_QUOTA_PERIOD: str = str(_POLICY["quota_period"])

TRIAL_HAS_TXT: bool = bool(_POLICY["txt"])
TRIAL_HAS_PDF: bool = bool(_POLICY["pdf"])
TRIAL_HAS_API: bool = bool(_POLICY["api"])
TRIAL_HAS_DASHBOARD: bool = bool(_POLICY["dashboard"])
TRIAL_HAS_TECHNICAL_SUPPORT: bool = bool(_POLICY["technical_support"])

TRIAL_PLAN_SLUG = "trial"

# Chave de período do `usage_tracking` para assinaturas em trial. Cabe no
# String(7) da coluna, e a unique (user_id, period) passa a dar exatamente UMA
# linha por usuário durante todo o trial — é isso que torna a janela vitalícia
# em vez de mensal, sem migration.
TRIAL_USAGE_PERIOD = "TRIAL"


def trial_policy() -> dict[str, Any]:
    """Cópia da política, para expor em testes e endpoints sem risco de mutação."""
    return {k: v for k, v in _POLICY.items() if not k.startswith("_")}
