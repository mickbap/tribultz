"""Smoke test para tools/architecture_audit.py.

A auditoria roda no CI atrás de continue-on-error (é informativa, não
bloqueia merge — ver knowledge/process/architecture-audit-policy.md no
Brain), o que mascarou um bug real por muito tempo: uma regex com
backtracking catastrófico em check_routers_vs_claude_md() travava a
ferramenta indefinidamente (nunca completou um run). Este teste garante que
uma regressão desse tipo estoura em segundos, não em CI silenciosamente
lento — o timeout aqui é a asserção.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "tools" / "architecture_audit.py"
BACKEND = REPO_ROOT / "backend"


def test_architecture_audit_completes_quickly():
    """Roda a auditoria de verdade (mesma invocação do CI/uso local) com um
    timeout curto. Um TimeoutExpired aqui indica uma regressão de
    performance (ex.: regex com backtracking catastrófico), não uma falha
    de achado — a auditoria pode legitimamente reportar findings (exit 1)."""
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=BACKEND,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError(
            "architecture_audit.py não completou em 30s — suspeita de "
            "regressão de performance (ex.: regex com backtracking "
            "catastrófico), não falha de achado."
        )

    assert result.returncode in (0, 1), (
        f"exit code inesperado {result.returncode} (0=sem achados, "
        f"1=achados encontrados). stderr:\n{result.stderr[-2000:]}"
    )
