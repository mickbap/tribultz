#!/usr/bin/env python3
"""Auditoria arquitetural automatizada — ADR-0013 / Ordem Técnica de
institucionalização da governança (2026-07-18) + Ordem Técnica de Auditoria
Contínua da Arquitetura (2026-07-18).

Verifica, contra o estado real do repositório (não contra memória de quem
audita):
  - Crews sem classificação institucional (header "Status:" no docstring)
  - Tasks Celery definidas mas ausentes de autodiscover_tasks
  - Ferramentas (app/crews/tools/) sem nenhum import fora do próprio arquivo
  - Routers reais vs. lista documentada no CLAUDE.md
  - Divergência entre o inventário do Brain (crews.md) e as Crews reais no
    código — best-effort, pulado com aviso se ../tribultz-brain não existir
    (a ausência do Brain não bloqueia a auditoria)

Cada achado carrega uma severidade (Crítico/Alto/Médio/Baixo) — a política
que define essa classificação vive em
knowledge/process/architecture-audit-policy.md no Brain; CATEGORY_SEVERITY
abaixo é a aplicação dela em código. Hoje a auditoria roda em modo
informativo no CI (não bloqueia merge nem quando encontra Crítico) — ver a
seção "Integração ao CI" da política.

Uso:
    cd backend && source .venv/bin/activate && python ../tools/architecture_audit.py

Saída: relatório em texto no stdout (mais anotações ::warning::/::error:: do
GitHub Actions quando GITHUB_ACTIONS=true). Exit code 0 se zero achados, 1 se
houver qualquer achado.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"


def _main_repo_root() -> Path:
    """Resolve the main repository root even when running from a git worktree.

    REPO_ROOT.parent is wrong inside a worktree — it resolves to the
    worktree's parent (e.g. .claude/worktrees/) instead of the actual
    sibling of tribultz/, which silently no-ops the Brain-sync check below.
    `git rev-parse --git-common-dir` always points at the main repo's .git,
    worktree or not. Falls back to REPO_ROOT if git is unavailable (e.g. a
    tarball checkout) — same soft-skip behavior as before this fix.
    """
    try:
        common_dir = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip()
        return (REPO_ROOT / common_dir).resolve().parent
    except Exception:
        return REPO_ROOT


BRAIN_ROOT = _main_repo_root().parent / "tribultz-brain"

SEVERITY_CRITICO = "Crítico"
SEVERITY_ALTO = "Alto"
SEVERITY_MEDIO = "Médio"
SEVERITY_BAIXO = "Baixo"

# Fonte da política: knowledge/process/architecture-audit-policy.md (Brain).
# Categoria sem entrada aqui cai em SEVERITY_MEDIO (default seguro em
# check_severity — nem alarme demais, nem passa despercebido).
CATEGORY_SEVERITY: dict[str, str] = {
    "crew-sem-classificacao": SEVERITY_CRITICO,
    "crew-fora-do-inventario-brain": SEVERITY_CRITICO,
    "crew-documentada-inexistente": SEVERITY_CRITICO,
    "router-documentado-inexistente": SEVERITY_CRITICO,
    "task-nao-registrada": SEVERITY_ALTO,
    "router-fora-da-doc": SEVERITY_ALTO,
    "celery-autodiscover-nao-encontrado": SEVERITY_ALTO,
    "claude-md-formato-inesperado": SEVERITY_ALTO,
    "ferramenta-orfa": SEVERITY_MEDIO,
    "brain-nao-encontrado": SEVERITY_BAIXO,
}


def severity_of(category: str) -> str:
    return CATEGORY_SEVERITY.get(category, SEVERITY_MEDIO)


@dataclass(frozen=True)
class Finding:
    category: str
    message: str


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── 1. Crews sem classificação institucional ────────────────────────────────


def check_crew_status_headers() -> list[Finding]:
    findings: list[Finding] = []
    crews_dir = BACKEND / "app" / "crews"
    for path in sorted(crews_dir.glob("*_crew.py")):
        text = _read(path)
        if "Status:" not in text:
            findings.append(
                Finding(
                    "crew-sem-classificacao",
                    f"{path.relative_to(REPO_ROOT)} não tem header 'Status:' no docstring "
                    "(ver knowledge/engineering/crews.md no Brain — toda Crew precisa de "
                    "Produção/Dormante/Experimental/Descontinuada declarado no código).",
                )
            )
    return findings


# ── 2. Tasks Celery ausentes de autodiscover_tasks ──────────────────────────


def check_celery_autodiscover() -> list[Finding]:
    findings: list[Finding] = []
    celery_app_path = BACKEND / "app" / "celery_app.py"
    tasks_dir = BACKEND / "app" / "tasks"

    source = _read(celery_app_path)
    match = re.search(r"autodiscover_tasks\(\[(.*?)\]\)", source, re.DOTALL)
    if not match:
        findings.append(
            Finding(
                "celery-autodiscover-nao-encontrado",
                f"Não achei a chamada autodiscover_tasks([...]) em {celery_app_path.relative_to(REPO_ROOT)} "
                "— verificação manual necessária.",
            )
        )
        return findings

    registered = set(re.findall(r'"([\w.]+)"', match.group(1)))
    registered_modules = {m.rsplit(".", 1)[-1] for m in registered}

    for path in sorted(tasks_dir.glob("task_*.py")):
        module_name = path.stem
        if module_name not in registered_modules:
            findings.append(
                Finding(
                    "task-nao-registrada",
                    f"backend/app/tasks/{path.name} define uma task mas o módulo não está em "
                    f"autodiscover_tasks (celery_app.py). Se for intencional (ex.: pendente de "
                    f"decisão de frequência), documentar em knowledge/engineering/crews.md ou "
                    f"architecture-inventory.md — não deixar implícito.",
                )
            )
    return findings


# ── 3. Ferramentas órfãs em app/crews/tools/ ────────────────────────────────


def check_orphan_tools() -> list[Finding]:
    findings: list[Finding] = []
    tools_dir = BACKEND / "app" / "crews" / "tools"
    if not tools_dir.exists():
        return findings

    all_py = list(BACKEND.rglob("*.py"))
    for tool_path in sorted(tools_dir.glob("*.py")):
        if tool_path.name == "__init__.py":
            continue
        module_stem = tool_path.stem
        used_elsewhere = False
        for other in all_py:
            if other == tool_path:
                continue
            try:
                text = _read(other)
            except (UnicodeDecodeError, OSError):
                continue
            if module_stem in text:
                used_elsewhere = True
                break
        if not used_elsewhere:
            findings.append(
                Finding(
                    "ferramenta-orfa",
                    f"backend/app/crews/tools/{tool_path.name} não é importado em nenhum outro "
                    "arquivo .py do backend — candidato a ferramenta órfã (ver Política de "
                    "Depreciação antes de remover).",
                )
            )
    return findings


# ── 4. Routers reais vs. CLAUDE.md ──────────────────────────────────────────


def check_routers_vs_claude_md() -> list[Finding]:
    findings: list[Finding] = []
    routers_dir = BACKEND / "app" / "routers"
    claude_md = REPO_ROOT / "CLAUDE.md"

    real_routers = {
        p.stem for p in routers_dir.glob("*.py") if p.stem != "__init__"
    }

    claude_text = _read(claude_md)
    # [\s\S]*? em vez de [^\n]+(?:\n\s+[^\n]+)*?: o quantificador aninhado
    # original tinha backtracking catastrófico — \s+ e [^\n]+ competiam pelos
    # mesmos espaços em runs de \n seguido de espaços, explodindo
    # exponencialmente (trava a auditoria inteira, mascarado no CI por
    # continue-on-error + timeout). [\s\S]*? não tem essa ambiguidade: casa
    # qualquer caractere sem precisar decidir entre dois grupos concorrentes.
    doc_match = re.search(r"app/routers/\s+\d+ routers[^\n]*—\s*([\s\S]*?)\.\s*Chat", claude_text)
    if not doc_match:
        findings.append(
            Finding(
                "claude-md-formato-inesperado",
                "Não consegui extrair a lista de routers documentada no CLAUDE.md com o "
                "regex esperado — formato do texto pode ter mudado; checagem manual.",
            )
        )
        return findings

    documented = {
        name.strip()
        for name in re.split(r",\s*", doc_match.group(1).replace("\n", " "))
        if name.strip()
    }

    missing_from_doc = real_routers - documented
    missing_from_code = documented - real_routers

    for name in sorted(missing_from_doc):
        findings.append(
            Finding(
                "router-fora-da-doc",
                f"backend/app/routers/{name}.py existe no código mas não está listado no CLAUDE.md.",
            )
        )
    for name in sorted(missing_from_code):
        findings.append(
            Finding(
                "router-documentado-inexistente",
                f"CLAUDE.md lista o router '{name}' mas backend/app/routers/{name}.py não existe "
                "— referência quebrada, atualizar a documentação.",
            )
        )
    return findings


# ── 5. Divergência Brain × produto (best-effort) ────────────────────────────


def check_brain_crews_sync() -> list[Finding]:
    findings: list[Finding] = []
    crews_md = BRAIN_ROOT / "knowledge" / "engineering" / "crews.md"
    if not BRAIN_ROOT.exists() or not crews_md.exists():
        findings.append(
            Finding(
                "brain-nao-encontrado",
                f"{BRAIN_ROOT} (ou crews.md dentro dele) não encontrado — checagem de "
                "sincronia Brain×produto pulada. Isso não bloqueia a auditoria; clone "
                "tribultz-brain como diretório irmão deste repo para habilitar.",
            )
        )
        return findings

    real_crews = {
        p.stem.replace("_crew", "")
        for p in (BACKEND / "app" / "crews").glob("*_crew.py")
    }

    # Uma linha por Crew documentada, pra checar o status na mesma linha —
    # "Descontinuada" é o único status em que "documentada mas sem arquivo"
    # é o comportamento correto (Política de Depreciação: nunca apagar a
    # linha do inventário), não uma divergência a reportar.
    brain_crews: set[str] = set()
    discontinued_brain_crews: set[str] = set()
    for line in _read(crews_md).splitlines():
        match = re.search(r"`(\w+)_crew\.py`", line)
        if not match:
            continue
        name = match.group(1)
        brain_crews.add(name)
        if "Descontinuada" in line:
            discontinued_brain_crews.add(name)

    for name in sorted(real_crews - brain_crews):
        findings.append(
            Finding(
                "crew-fora-do-inventario-brain",
                f"{name}_crew.py existe no código mas não encontrei menção em "
                "knowledge/engineering/crews.md — atualizar o inventário no Brain.",
            )
        )
    for name in sorted(brain_crews - real_crews - discontinued_brain_crews):
        findings.append(
            Finding(
                "crew-documentada-inexistente",
                f"knowledge/engineering/crews.md menciona '{name}_crew.py' como não-Descontinuada "
                "mas o arquivo não existe no código — Brain desatualizado ou remoção sem registro.",
            )
        )
    return findings


# ── main ─────────────────────────────────────────────────────────────────


CHECKS = [
    ("Crews sem classificação institucional", check_crew_status_headers),
    ("Tasks Celery ausentes de autodiscover_tasks", check_celery_autodiscover),
    ("Ferramentas órfãs em app/crews/tools/", check_orphan_tools),
    ("Routers reais vs. CLAUDE.md", check_routers_vs_claude_md),
    ("Sincronia Brain × produto (Crews)", check_brain_crews_sync),
]


def _emit_gha_annotation(finding: Finding) -> None:
    level = "error" if severity_of(finding.category) == SEVERITY_CRITICO else "warning"
    title = f"[{severity_of(finding.category)}] {finding.category}"
    message = finding.message.replace("\n", " ").replace("::", ": ")
    print(f"::{level} title={title}::{message}")


def main() -> int:
    in_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    all_findings: list[Finding] = []
    print("=" * 70)
    print("Auditoria Arquitetural — Tribultz (ADR-0013)")
    print("=" * 70)

    for title, check_fn in CHECKS:
        findings = check_fn()
        all_findings.extend(findings)
        status = "OK" if not findings else f"{len(findings)} achado(s)"
        print(f"\n[{status}] {title}")
        for f in findings:
            print(f"  - [{severity_of(f.category)}] ({f.category}) {f.message}")
            if in_ci:
                _emit_gha_annotation(f)

    print("\n" + "=" * 70)
    real_findings = [f for f in all_findings if f.category not in ("brain-nao-encontrado",)]
    if real_findings:
        by_severity: dict[str, int] = {}
        for f in real_findings:
            sev = severity_of(f.category)
            by_severity[sev] = by_severity.get(sev, 0) + 1
        breakdown = ", ".join(
            f"{by_severity[s]} {s}"
            for s in (SEVERITY_CRITICO, SEVERITY_ALTO, SEVERITY_MEDIO, SEVERITY_BAIXO)
            if s in by_severity
        )
        print(f"RESULTADO: {len(real_findings)} achado(s) que exigem atenção ({breakdown}).")
        return 1
    print("RESULTADO: nenhum achado. Arquitetura consistente com o inventário.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
