#!/usr/bin/env python3
"""Publica uma entrada na tabela `news` a partir do último merge em `main`.

Disparado pelo workflow `.github/workflows/publish-news.yml` em todo push para main.

Regime OPT-IN ESTRITO (16/08/2026, contenção do incidente de exposição — Lote 0
da ordem QA→Techlead). Antes, a ausência da seção `## Changelog público` no PR
fazia o script publicar o primeiro parágrafo do body INTERNO do PR — todo merge
feat/fix/security em `main` virava entrada pública com conteúdo de processo.
Agora **só publica com a seção declarada explicitamente**; não há fallback.

Lógica:
1. Lê o commit em $COMMIT_SHA via `git show`
2. Se for revert / merge sem mensagem útil → ignora
3. Identifica o tipo (feat/fix/security) — só esses três viram news
4. Tenta extrair o número do PR (#N) e busca o body do PR via `gh`
5. Se o PR tem label `no-changelog` → pula
6. Se (e somente se) o PR body tem seção `## Changelog público` → publica essa
   seção como description. Sem a seção (ou sem PR/sem body) → `[skip]`, exit 0
7. Denylist de termos internos sobre título+descrição → aborta (exit 1) se casar
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
# Squash merge do GitHub acrescenta " (#N)" ao FIM do assunto.
SQUASH_PR_RE = re.compile(r"\(#(\d+)\)\s*$")
PUBLIC_CHANGELOG_RE = re.compile(
    r"##\s*Changelog\s+p[úu]blico\s*\n+(.+?)(?=\n##|\Z)",
    re.IGNORECASE | re.DOTALL,
)
PUBLIC_TITLE_RE = re.compile(r"^\s*T[íi]tulo:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
PUBLISHABLE_TYPES = {"feat", "fix", "security"}
TYPE_TO_CATEGORY = {
    "feat": "Feature",
    "fix": "Fix",
    "security": "Security",
}

# Rede de segurança ATRÁS do opt-in (L0.2): mesmo com a seção `## Changelog
# público` declarada, vocabulário de processo interno não sai daqui. Casar
# qualquer padrão aborta a publicação com exit 1 — falhar o workflow é o lado
# seguro: o autor reescreve a seção em linguagem de cliente e re-dispara.
INTERNAL_TERM_PATTERNS: list[str] = [
    r"\bdeploys?\b",
    r"\bbranch(?:es)?\b",
    r"\bmigrations?\b",
    r"\balembic\b",
    r"\bssh\b",
    r"\bredis\b",
    r"\bcelery\b",
    r"\bworkers?\b",
    r"\bbeat\b",
    r"\brounds?\s*\d+\b",
    r"\bgates?\b",
    r"\bPR\s*#?\s*\d+\b",
    r"\bmain\b",
    r"\bmagalu\b",
    r"\btribultz-(?:api|vm|db)\b",
    r"\bdocker\b",
    r"\bcompose\b",
    r"\bpytest\b",
    r"\bruff\b",
    r"\bstaging\b",
    r"\brollbacks?\b",
    r"\bhotfix\b",
    r"\bworktree\b",
]
INTERNAL_TERM_RE = [re.compile(p, re.IGNORECASE) for p in INTERNAL_TERM_PATTERNS]


CODE_FENCE_RE = re.compile(r"^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*$", re.MULTILINE | re.DOTALL)


def strip_code_fences(text: str) -> str:
    """Remove blocos de código cercados antes de procurar a seção pública.

    Um PR que DOCUMENTA a sintaxe da seção — mostrando `## Changelog público`
    dentro de um bloco de exemplo — não está declarando nada; está explicando.
    Sem esta limpeza, o exemplo virava a publicação: foi o que aconteceu no
    #649, cujo corpo trazia o exemplo do recurso recém-criado e acabou
    publicando o texto de demonstração no feed do cliente.
    """
    return CODE_FENCE_RE.sub("", text or "")


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
    limpo = strip_code_fences(pr_body)
    # Última seção, não a primeira: se ainda restar mais de uma, a declaração
    # real do autor tende a vir depois da explicação. Mesma classe de defeito da
    # detecção do número do PR, que pegava o primeiro `#N` (a issue).
    achados = list(PUBLIC_CHANGELOG_RE.finditer(limpo))
    if not achados:
        return None
    text = achados[-1].group(1).strip()
    return text or None


def detect_pr_number(subject: str, body: str) -> Optional[str]:
    """Número do PR do merge — o do FIM do assunto, não o primeiro que aparecer.

    Nossos títulos já citam a issue que o PR fecha, e o squash merge acrescenta
    o número do PR ao fim. O assunto final tem dois números:

        feat(billing): Trial com fonte única … (#635) (#647)
                                                 ↑issue   ↑PR

    A busca antiga pegava o PRIMEIRO — a issue. `gh pr view <issue>` falha
    ("Could not resolve to a PullRequest"), o script seguia sem body e pulava
    reportando "PR sem seção '## Changelog público'", mascarando a causa real.
    Efeito: entre 16 e 17/08 nenhum merge publicou, inclusive cinco que traziam
    a seção corretamente declarada.

    Consequência secundária, também corrigida: a checagem da label
    `no-changelog` consultava o PR errado.
    """
    m = SQUASH_PR_RE.search(subject.strip())
    if m:
        return m.group(1)
    # Sem o sufixo de squash (merge commit comum), fica o último #N citado —
    # ainda melhor que o primeiro, que tende a ser a issue.
    todos = PR_NUMBER_RE.findall(f"{subject}\n{body}")
    return todos[-1] if todos else None


def extract_public_title(pr_body: str) -> Optional[str]:
    """Título público declarado na seção, na forma `Título: …`.

    Sem isso o título vem do assunto do commit, que é interno por convenção
    (Conventional Commits, escopo técnico, nome de arquivo). O opt-in do Lote 0
    curava só a DESCRIÇÃO — e a primeira publicação do regime novo saiu com a
    descrição em linguagem de cliente e o título dizendo "Publicador do
    changelog lia o número da ISSUE, não o do PR".

    A denylist não pegava: o título era internamente irrelevante sem usar
    nenhuma palavra proibida. Vocabulário é filtrável; propósito não.
    """
    achados = list(PUBLIC_CHANGELOG_RE.finditer(strip_code_fences(pr_body)))
    if not achados:
        return None
    m = PUBLIC_TITLE_RE.search(achados[-1].group(1))
    if not m:
        return None
    titulo = m.group(1).strip()
    return titulo[:200] or None


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


def build_description(pr_body: str) -> Optional[str]:
    """Descrição pública = a seção `## Changelog público` do PR, ou nada.

    Opt-in estrito: sem a seção não há publicação. Não existe fallback para o
    body interno do PR nem para texto genérico — era exatamente esse caminho
    que vazava conteúdo de processo para o feed público.
    """
    override = extract_public_changelog(pr_body)
    if not override:
        return None
    # A linha `Título: …` governa o título, não entra no corpo.
    override = PUBLIC_TITLE_RE.sub("", override).strip()
    if not override:
        return None
    # Limpa markdown básico (mantém legível)
    override = re.sub(r"^[-*]\s*", "• ", override, flags=re.MULTILINE)
    return override[:2000]


def find_internal_terms(*texts: str) -> list[str]:
    """Retorna os termos internos encontrados no payload (vazio = limpo)."""
    hits: list[str] = []
    for text in texts:
        if not text:
            continue
        for pattern in INTERNAL_TERM_RE:
            m = pattern.search(text)
            if m and m.group(0) not in hits:
                hits.append(m.group(0))
    return hits


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
        print("[skip] subject não segue Conventional Commits — ignorando")
        return 0

    if parsed["type"] not in PUBLISHABLE_TYPES:
        print(f"[skip] tipo '{parsed['type']}' não é publicado (só feat/fix/security)")
        return 0

    # Detecta PR via #N no subject ou body
    body = get_commit_body(sha)
    pr_number = detect_pr_number(subject, body)
    pr_data = {}
    if pr_number:
        print(f"[info] PR detectado: #{pr_number}")
        pr_data = fetch_pr_data(pr_number)
        if has_no_changelog_label(pr_data):
            print(f"[skip] PR #{pr_number} tem label 'no-changelog'")
            return 0

    # Opt-in estrito: sem seção `## Changelog público` declarada no PR, nada sai.
    description = build_description(pr_data.get("body", "") or "")
    if not description:
        print("[skip] PR sem seção '## Changelog público' — nada a publicar")
        return 0

    title = extract_public_title(pr_data.get("body", "") or "") or build_title(
        parsed, parsed.get("scope")
    )
    category = TYPE_TO_CATEGORY[parsed["type"]]

    # Rede de segurança: vocabulário interno nunca chega ao feed público.
    internal_hits = find_internal_terms(title, description)
    if internal_hits:
        print(
            "[err] payload contém termos internos "
            f"{internal_hits!r} — publicação abortada. Reescreva a seção "
            "'## Changelog público' (e o título do commit) em linguagem de cliente.",
            file=sys.stderr,
        )
        return 1

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
