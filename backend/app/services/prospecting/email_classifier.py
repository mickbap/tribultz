"""Classifica o domínio de e-mail de um escritório contábil (PO-2026-07-SALES-001,
Fase 1). Determinístico, sem chamada externa nem IA — exigência explícita da PO
para o pré-score.

Categorias: ausente | gratuito | dominio_generico | dominio_nominal.
"""

from __future__ import annotations

import re
import unicodedata

FREE_EMAIL_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "hotmail.com", "outlook.com", "live.com", "yahoo.com",
    "yahoo.com.br", "bol.com.br", "uol.com.br", "terra.com.br", "icloud.com",
    "msn.com", "ig.com.br", "globo.com", "oi.com.br", "r7.com",
})

# Sufixos legais/genéricos descartados ao tokenizar a razão social/nome fantasia —
# não ajudam a decidir se um domínio "deriva" do nome da empresa.
_GENERIC_SUFFIXES: frozenset[str] = frozenset({
    "ltda", "me", "epp", "eireli", "ss", "sa", "individual", "contabil",
    "contabilidade", "assessoria", "servicos", "consultoria", "contadores",
    "escritorio", "associados", "e", "de", "da", "do", "dos", "das",
})

_KNOWN_TLDS = (
    ".com.br", ".net.br", ".org.br", ".adv.br", ".eng.br", ".com", ".net", ".org",
)

_MIN_TOKEN_LEN = 4


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _normalize_tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    cleaned = _strip_accents(text).lower()
    raw_tokens = re.split(r"[^a-z0-9]+", cleaned)
    return {
        t for t in raw_tokens
        if len(t) >= _MIN_TOKEN_LEN and t not in _GENERIC_SUFFIXES
    }


def _strip_known_tld(domain: str) -> str:
    for tld in _KNOWN_TLDS:
        if domain.endswith(tld):
            return domain[: -len(tld)]
    # TLD desconhecido: cai no primeiro rótulo antes do primeiro ponto.
    return domain.split(".", 1)[0]


def extract_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[-1].strip().lower()
    return domain or None


def classify_domain(
    email: str | None,
    razao_social: str | None = None,
    nome_fantasia: str | None = None,
) -> str:
    """Retorna: ausente | gratuito | dominio_generico | dominio_nominal."""
    domain = extract_domain(email)
    if domain is None:
        return "ausente"
    if domain in FREE_EMAIL_DOMAINS:
        return "gratuito"

    root = _strip_known_tld(domain)
    tokens = _normalize_tokens(razao_social) | _normalize_tokens(nome_fantasia)
    if any(t in root or root in t for t in tokens):
        return "dominio_nominal"
    return "dominio_generico"
