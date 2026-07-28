"""Classifica o e-mail de um escritório contábil (PO-2026-07-SALES-001, Fase 1;
tipo do endereço adicionado pela Ordem Complementar, item 6). Determinístico,
sem chamada externa nem IA.

Dois conceitos independentes, cada um com sua própria classificação:
- classify_domain(): ausente | gratuito | dominio_generico | dominio_nominal.
- classify_email_type(): contato | comercial | financeiro | fiscal | suporte |
  nome_sobrenome | outro | ausente — peso baixo na rubrica, só para desempate.
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


# Prefixos de papel/função do endereço (parte antes do @) — independente do
# domínio. Ordem importa: "fiscal" é checado antes de "contabil" fazer parte
# de "contabilidade" via _GENERIC_SUFFIXES não se aplicar aqui (lista própria).
_ROLE_PREFIXES: dict[str, tuple[str, ...]] = {
    "fiscal": ("fiscal", "tributos", "tributario"),
    "financeiro": ("financeiro", "cobranca", "faturamento", "boleto"),
    "comercial": ("comercial", "vendas", "sales", "negocios", "orcamento"),
    "suporte": ("suporte", "support", "atendimento", "sac", "ajuda"),
    "contato": ("contato", "contact", "info", "geral"),
}


def _looks_like_personal_name(local: str) -> bool:
    """Heurística determinística para "nome.sobrenome" — sem lista de nomes
    própria: dois ou mais tokens alfabéticos (>=2 letras) separados por
    ./_/- e nada mais (evita casar "joao123" ou "contato.geral")."""
    parts = re.split(r"[._-]", local)
    if len(parts) < 2:
        return False
    return all(p.isalpha() and len(p) >= 2 for p in parts)


def classify_email_type(email: str | None) -> str:
    """Retorna: ausente | fiscal | financeiro | comercial | suporte | contato |
    nome_sobrenome | outro. Peso baixo na rubrica — só auxilia desempate entre
    registros semelhantes (Ordem Complementar, item 6)."""
    if not email or "@" not in email:
        return "ausente"
    local = _strip_accents(email.split("@", 1)[0].strip().lower())
    if not local:
        return "ausente"

    for type_name, prefixes in _ROLE_PREFIXES.items():
        if any(local == p or local.startswith(p) for p in prefixes):
            return type_name

    if _looks_like_personal_name(local):
        return "nome_sobrenome"

    return "outro"
