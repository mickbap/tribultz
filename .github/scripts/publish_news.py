#!/usr/bin/env python3
"""Publica uma entrada na tabela `news` a partir do último merge em `main`.

Disparado pelo workflow `.github/workflows/publish-news.yml` em todo push para main.

Lógica:
1. Lê o commit em $COMMIT_SHA via `git show`
2. Se for revert / merge sem mensagem útil → ignora
3. Identifica o tipo (feat/fix/security) — só esses três viram news
4. Tenta extrair o número do PR (#N) e busca o body do PR via `gh`
5. Se o PR tem label `no-changelog` → pula
6. Se o PR body tem seção `## Changelog público` → usa como description (override)
7. Caso contrário, monta description automaticamente
8. POST `/api/v1/news` com Bearer token

Variáveis de ambiente:
- COMMIT_SHA          (obrigatório)
- BACKEND_URL         (ex.: https://api.tribultz.com.br)
- NEWS_PUBLISH_TOKEN  (token do secret)
- GH_TOKEN            (para `gh` CLI buscar PR body/labels)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Optional

import httpx


CONVENTIONAL_PREFIX_RE = re.compile(
    r"^(?P<type>feat|fix|chore|docs|refactor|test|ci|build|style|perf|security)"
    r"(?:\((?P<scope>[^)]+)\))?:\s*(?P<subject>.+)$"
)
PR_NUMBER_RE = re.compile(r"#(\d+)")
PUBLIC_CHANGELOG_RE = re.compile(
    r"##\s*Changelog\s+p[úu]blico\s*\n+(.+?)(?=\n##|\Z)",
    re.IGNORECASE | re.DOTALL,
)
PUBLISHABLE_TYPES = {"feat", "fix", "security"}
TYPE_TO_CATEGORY = {
    "feat": "Feature",
    "fix": "Fix",
    "security": "Security",
}


def run(cmd: list[str], **kwargs) -> str:
    """Roda comando e retorna stdout. Nunca levanta — retorna '' em erro."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
        if result.returncode != 0:
            print(f"[warn] {' '.join(cmd)} -> exit {result.returncode}: {result.stderr.strip()}", file=sys.stderr)
            return ""
        return result.stdout.strip()
    except FileNotFoundError as e:
        print(f"[warn] command not found: {e}", file=sys.stderr)
        return ""


def get_commit_subject(sha: str) -> str:
    return run(["git", "show", "-s", "--format=%s", sha])


def get_commit_body(sha: str) -> str:
    return run(["git", "show", "-s", "--format=%b", sha])


def parse_subject(subject: str) -> Optional[dict]:
    """Extrai type/scope/clean_subject do commit message."""
    m = CONVENTIONAL_PREFIX_RE.match(subject.strip())
    if not m:
        return None
    return {
        "type": m.group("type").lower(),
        "scope": m.group("scope"),
        "subject_clean": m.group("subject").strip(),
    }


def fetch_pr_data(pr_number: str) -> dict:
    """Busca body + labels do PR via `gh`. Retorna dict vazio em falha."""
    raw = run(["gh", "pr", "view", pr_number, "--json", "body,labels,title"])
    if not raw:
        return {}
    try:
        import json
        return json.loads(raw)
    except Exception as e:
        print(f"[warn] failed to parse PR data: {e}", file=sys.stderr)
        return {}


def has_no_changelog_label(pr_data: dict) -> bool:
    labels = pr_data.get("labels") or []
    return any(lbl.get("name") == "no-changelog" for lbl in labels)


def extract_public_changelog(pr_body: str) -> Optional[str]:
    """Se o PR body tem seção '## Changelog público', retorna o conteúdo."""
    if not pr_body:
        return None
    m = PUBLIC_CHANGELOG_RE.search(pr_body)
    if not m:
        return None
    text = m.group(1).strip()
    return text or None


def build_title(parsed: dict, scope_label: Optional[str]) -> str:
    """Monta título amigável a partir do commit parseado."""
    subject = parsed["subject_clean"]
    # Capitaliza primeira letra
    if subject and subject[0].islower():
        subject = subject[0].upper() + subject[1:]
    # Remove sufixos tipo (#244), (#241 #240), (#241, #240) — loop cobre múltiplos
    while True:
        new_subject = re.sub(r"\s*\(#\d+(?:[\s,]+#\d+)*\)\s*$", "", subject).strip()
        if new_subject == subject:
            break
        subject = new_subject
    # Trunca em 200 chars (limite da coluna)
    if len(subject) > 200:
        subject = subject[:197].rstrip() + "..."
    return subject


def build_description(parsed: dict, pr_body: str) -> str:
    """Constrói descrição a partir do override do PR ou do body."""
    override = extract_public_changelog(pr_body)
    if override:
        # Limpa markdown básico (mantém legível)
        override = re.sub(r"^[-*]\s*", "• ", override, flags=re.MULTILINE)
        return override[:2000]

    # Fallback: pega o primeiro parágrafo significativo do PR body
    if pr_body:
        # Remove headers, pega o primeiro parágrafo real
        for chunk in pr_body.split("\n\n"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if chunk.startswith("##") or chunk.startswith("Closes") or chunk.startswith("Fixes"):
                continue
            # Limpa marcações markdown comuns
            chunk = re.sub(r"^#+\s*", "", chunk)
            chunk = re.sub(r"`([^`]+)`", r"\1", chunk)
            chunk = re.sub(r"\*\*([^*]+)\*\*", r"\1", chunk)
            chunk = re.sub(r"^[-*]\s*", "• ", chunk, flags=re.MULTILINE)
            return chunk[:2000]

    # Último recurso: descrição genérica
    type_label = {"feat": "Nova funcionalidade", "fix": "Correção", "security": "Atualização de segurança"}
    return type_label.get(parsed["type"], "Atualização") + " disponível na plataforma."


def main() -> int:
    sha = os.environ.get("COMMIT_SHA", "").strip()
    backend_url = os.environ.get("BACKEND_URL", "").strip().rstrip("/")
    token = os.environ.get("NEWS_PUBLISH_TOKEN", "").strip()

    if not sha:
        print("[err] COMMIT_SHA not set", file=sys.stderr)
        return 1
    if not backend_url:
        print("[skip] BACKEND_URL secret not configured — pulando publicação")
        return 0
    if not token:
        print("[skip] NEWS_PUBLISH_TOKEN secret not configured — pulando publicação")
        return 0

    subject = get_commit_subject(sha)
    if not subject:
        print(f"[err] could not read commit {sha}", file=sys.stderr)
        return 1

    print(f"[info] commit subject: {subject}")

    parsed = parse_subject(subject)
    if not parsed:
        print(f"[skip] subject não segue Conventional Commits — ignorando")
        return 0

    if parsed["type"] not in PUBLISHABLE_TYPES:
        print(f"[skip] tipo '{parsed['type']}' não é publicado (só feat/fix/security)")
        return 0

    # Detecta PR via #N no subject ou body
    body = get_commit_body(sha)
    full_text = f"{subject}\n{body}"
    pr_match = PR_NUMBER_RE.search(full_text)
    pr_data = {}
    if pr_match:
        pr_number = pr_match.group(1)
        print(f"[info] PR detectado: #{pr_number}")
        pr_data = fetch_pr_data(pr_number)
        if has_no_changelog_label(pr_data):
            print(f"[skip] PR #{pr_number} tem label 'no-changelog'")
            return 0

    title = build_title(parsed, parsed.get("scope"))
    description = build_description(parsed, pr_data.get("body", "") or "")
    category = TYPE_TO_CATEGORY[parsed["type"]]

    print(f"[info] vai publicar: category={category} title={title!r}")
    print(f"[info] description (primeiros 200 chars): {description[:200]!r}")

    payload = {"title": title, "description": description, "category": category}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        resp = httpx.post(
            f"{backend_url}/api/v1/news",
            json=payload,
            headers=headers,
            timeout=15.0,
        )
    except httpx.HTTPError as e:
        print(f"[err] HTTP erro chamando backend: {e}", file=sys.stderr)
        return 1

    if resp.status_code in (200, 201):
        kind = "criada" if resp.status_code == 201 else "deduplicada (já existia)"
        print(f"[ok] news {kind} — id={resp.json().get('id')}")
        return 0

    print(f"[err] backend retornou {resp.status_code}: {resp.text}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
