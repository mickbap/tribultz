#!/usr/bin/env python3
"""Auto-generate frontend/src/data/changelog.json from closed GitHub issues.

Triggered by the changelog GitHub Action. Reads issues via `gh` CLI,
groups by sprint tag [S<N>-*], and writes a structured JSON file.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = REPO_ROOT / "frontend" / "src" / "data" / "changelog.json"

SPRINT_RE = re.compile(r"\[S(\d+)-(\d+)\]\s*(.+)")

# Map issue labels to changelog entry type
LABEL_TO_TYPE: dict[str, str] = {
    "enhancement": "melhoria",
    "bug": "correcao",
}

SPRINT_META: dict[str, dict[str, str]] = {
    "6": {
        "title": "Sprint 6 \u2014 Export & Evidencias",
        "summary": "Exportacao de evidencias, pacotes ZIP e discovery com contabilidade.",
    },
    "7": {
        "title": "Sprint 7 \u2014 Motor Deterministico",
        "summary": "10 regras fiscais deterministicas com evidencias auditaveis.",
    },
    "8": {
        "title": "Sprint 8 \u2014 API Mode & Integracao",
        "summary": "Backend real conectado, CrewAI robusto e relatorios auditaveis.",
    },
    "9": {
        "title": "Sprint 9 \u2014 Governanca & Seguranca",
        "summary": "Multi-tenant, LGPD, autenticacao robusta e seguranca de producao.",
    },
    "10": {
        "title": "Sprint 10 \u2014 Release Candidate",
        "summary": "Polimento final, performance e preparacao para producao.",
    },
}


def fetch_closed_issues() -> list[dict]:
    """Fetch all closed issues from GitHub via gh CLI."""
    result = subprocess.run(
        [
            "gh", "issue", "list",
            "--state", "closed",
            "--limit", "200",
            "--json", "number,title,labels,closedAt",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"gh issue list failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def classify_type(labels: list[dict]) -> str:
    """Determine entry type from issue labels."""
    names = {lbl["name"] for lbl in labels}
    for label_name, entry_type in LABEL_TO_TYPE.items():
        if label_name in names:
            return entry_type
    return "novo"


def classify_scope(labels: list[dict]) -> list[str]:
    """Determine scope (frontend/backend) from labels."""
    names = {lbl["name"] for lbl in labels}
    scope = []
    if "frontend" in names:
        scope.append("frontend")
    if "backend" in names:
        scope.append("backend")
    return scope if scope else ["backend"]


def build_changelog(issues: list[dict]) -> dict:
    """Group issues by sprint and build the changelog structure."""
    sprints: dict[str, list[dict]] = defaultdict(list)
    sprint_dates: dict[str, str] = {}

    for issue in issues:
        m = SPRINT_RE.match(issue["title"])
        if not m:
            continue

        sprint_num = m.group(1)
        desc = m.group(3).strip()
        closed_at = issue["closedAt"][:10] if issue.get("closedAt") else "2026-01-01"

        entry = {
            "type": classify_type(issue.get("labels", [])),
            "text": desc,
            "scope": classify_scope(issue.get("labels", [])),
        }
        sprints[sprint_num].append(entry)

        # Keep most recent close date per sprint
        if sprint_num not in sprint_dates or closed_at > sprint_dates[sprint_num]:
            sprint_dates[sprint_num] = closed_at

    # Build sorted output (newest sprint first)
    result = []
    for snum in sorted(sprints.keys(), key=int, reverse=True):
        meta = SPRINT_META.get(snum, {
            "title": f"Sprint {snum}",
            "summary": "",
        })
        result.append({
            "id": f"s{snum}",
            "title": meta["title"],
            "date": sprint_dates.get(snum, "2026-01-01"),
            "summary": meta["summary"],
            "entries": sprints[snum],
        })

    return {"sprints": result}


def main():
    issues = fetch_closed_issues()
    changelog = build_changelog(issues)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(changelog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(changelog['sprints'])} sprints to {OUTPUT}")


if __name__ == "__main__":
    main()
