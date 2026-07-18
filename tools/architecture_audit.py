#!/usr/bin/env python3
"""Auditoria arquitetural automatizada — ADR-0013 / Ordem Técnica de
institucionalização da governança (2026-07-18).

Verifica, contra o estado real do repositório (não contra memória de quem
audita):
  - Crews sem classificação institucional (header "Status:" no docstring)
  - Tasks Celery definidas mas ausentes de autodiscover_tasks
  - Ferramentas (app/crews/tools/) sem nenhum import fora do próprio arquivo
  - Routers reais vs. lista documentada no CLAUDE.md
  - Divergência entre o inventário do Brain (crews.md) e as Crews reais no
    código — best-effort, pulado com aviso se ../tribultz-brain não existir
    (a ausência do Brain não bloqueia a auditoria)

Uso:
    cd backend && source .venv/bin/activate && python ../tools/architecture_audit.py

Saída: relatório em texto no stdout. Exit code 0 se zero achados, 1 se houver
qualquer achado (para uso futuro em CI — ver docstring do módulo, PARTE III
da Ordem Técnica: a ausência de integração ao CI não bloqueia esta entrega).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
BRAIN_ROOT = REPO_ROOT.parent / "tribultz-brain"


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
    doc_match = re.search(r"app/routers/\s+\d+ routers[^\n]*—\s*([^\n]+(?:\n\s+[^\n]+)*?)\.\s*Chat", claude_text)
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


def main() -> int:
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
            print(f"  - ({f.category}) {f.message}")

    print("\n" + "=" * 70)
    real_findings = [f for f in all_findings if f.category not in ("brain-nao-encontrado",)]
    if real_findings:
        print(f"RESULTADO: {len(real_findings)} achado(s) que exigem atenção.")
        return 1
    print("RESULTADO: nenhum achado. Arquitetura consistente com o inventário.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
