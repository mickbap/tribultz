#!/usr/bin/env python3
"""Backfill de notícias a partir do histórico recente de commits em main.

Uso (na VM Magalu, dentro do container backend OU com .env carregado):

    python -m backend.scripts.backfill_news --limit 30

Lê os últimos N commits de `git log main`, parseia mensagens Conventional Commits,
e insere entradas na tabela `news` para todo `feat:` / `fix:` / `security:`.

Idempotente: se uma entrada com o mesmo título já existe (qualquer data), pula.

Roda OFFLINE (acesso direto ao banco via SQLAlchemy) — não precisa do endpoint POST.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Permite rodar tanto como módulo (`python -m`) quanto direto (`python scripts/backfill_news.py`)
THIS_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = THIS_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.news import News  # noqa: E402


CONVENTIONAL_RE = re.compile(
    r"^(?P<type>feat|fix|security)"
    r"(?:\([^)]+\))?:\s*(?P<subject>.+)$"
)
# Limpa sufixos como "(#243)", "(#241 #240)", "(#241, #240)" no final
PR_SUFFIX_RE = re.compile(r"\s*\(#\d+(?:[\s,]+#\d+)*\)\s*$")
TYPE_TO_CATEGORY = {
    "feat": "Feature",
    "fix": "Fix",
    "security": "Security",
}


def get_recent_commits(limit: int) -> list[dict]:
    """Retorna lista de {sha, subject} dos últimos N commits de origin/main.

    Faz `git fetch origin main` antes de ler para garantir que estamos olhando
    o estado canônico do servidor — independente de em qual branch o cwd está.
    """
    fetch_result = subprocess.run(
        ["git", "fetch", "origin", "main"],
        capture_output=True,
        text=True,
        cwd=BACKEND_ROOT.parent,
    )
    if fetch_result.returncode != 0:
        print(f"[err] git fetch falhou: {fetch_result.stderr}", file=sys.stderr)
        return []

    result = subprocess.run(
        ["git", "log", f"-{limit}", "--pretty=format:%H||%s", "origin/main"],
        capture_output=True,
        text=True,
        cwd=BACKEND_ROOT.parent,  # repo root
    )
    if result.returncode != 0:
        print(f"[err] git log falhou: {result.stderr}", file=sys.stderr)
        return []

    commits = []
    for line in result.stdout.strip().splitlines():
        if "||" not in line:
            continue
        sha, subject = line.split("||", 1)
        commits.append({"sha": sha.strip(), "subject": subject.strip()})
    return commits


def parse_commit(subject: str) -> dict | None:
    m = CONVENTIONAL_RE.match(subject)
    if not m:
        return None
    clean = m.group("subject").strip()
    # Aplica em loop pra cobrir "(#241 #240) (#243)" (dois grupos)
    while True:
        new_clean = PR_SUFFIX_RE.sub("", clean).strip()
        if new_clean == clean:
            break
        clean = new_clean
    if clean and clean[0].islower():
        clean = clean[0].upper() + clean[1:]
    if len(clean) > 200:
        clean = clean[:197].rstrip() + "..."
    return {
        "type": m.group("type").lower(),
        "title": clean,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Backfill news a partir do histórico recente de origin/main.",
    )
    ap.add_argument("--limit", type=int, default=30, help="Quantos commits varrer (default: 30)")
    ap.add_argument("--dry-run", action="store_true", help="Não escreve no banco — só lista")
    args = ap.parse_args()

    commits = get_recent_commits(args.limit)
    if not commits:
        print("[skip] nenhum commit encontrado")
        return 0

    print(f"[info] varrendo {len(commits)} commits...")

    inserted = 0
    skipped_dup = 0
    skipped_type = 0

    with SessionLocal() as db:
        for c in commits:
            parsed = parse_commit(c["subject"])
            if not parsed:
                skipped_type += 1
                continue

            existing = db.scalar(select(News).where(News.title == parsed["title"]))
            if existing is not None:
                skipped_dup += 1
                continue

            category = TYPE_TO_CATEGORY[parsed["type"]]
            description_label = {
                "Feature": "Nova funcionalidade disponível na plataforma.",
                "Fix": "Correção aplicada para garantir conformidade e estabilidade.",
                "Security": "Atualização de segurança aplicada.",
            }[category]

            print(f"[+ {category:<7}] {parsed['title']}")
            if not args.dry_run:
                db.add(News(
                    title=parsed["title"],
                    description=description_label,
                    category=category,
                ))
            inserted += 1

        if not args.dry_run:
            db.commit()

    print(
        f"\n[summary] inseridos={inserted} duplicados={skipped_dup} "
        f"tipos_ignorados={skipped_type} dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
