"""Resolução determinística de identidade de pessoa — DEC-5 (Round 4 §1).

A unidade de proteção contra retomada da automação é a PESSOA, não o lead
externo: novo external_lead_id ≠ nova permissão de abordagem. A resolução usa
SOMENTE igualdade exata pós-normalização (e-mail e/ou LinkedIn) — matching
probabilístico é proibido ("falso positivo também é incidente comercial").

Casos de borda decididos aqui (e testados):
- chaves apontando para identidades DIFERENTES ⇒ CONFLITO: nada é mesclado,
  nada é criado; fail-safe bloqueia outbound até curadoria humana.
- identidade encontrada por uma chave e a outra chave livre ⇒ enriquecimento
  determinístico (preenche a chave vazia); jamais sobrescreve chave existente.
- dado compartilhado por pessoas legitimamente distintas (ex.: e-mail comum):
  colapsa na mesma identidade POR DESENHO (e-mail é chave única de
  pessoa). Modo de falha é conservador — bloqueia
  outbound a mais, nunca a menos; separação exige curadoria humana.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.models.crm_handoff import CrmLeadLink, CrmPersonIdentity

#: estados de ownership que protegem a pessoa contra automação (DEC-1 + DEC-5)
PROTECTED_OWNERSHIP_STATES: frozenset[str] = frozenset({"HANDOFF_REQUESTED", "HUMAN_OWNED"})


def normalize_email(raw: Optional[str]) -> Optional[str]:
    """Normalização determinística: trim + lowercase. Sem heurística de provedor."""
    if raw is None:
        return None
    v = raw.strip().lower()
    if not v or "@" not in v:
        return None
    return v


def normalize_linkedin(raw: Optional[str]) -> Optional[str]:
    """Canonicaliza URL/handle de LinkedIn de forma determinística.

    'https://www.LinkedIn.com/in/Foo-Bar/?utm=x', 'linkedin.com/in/foo-bar' e
    'in/foo-bar' → 'in/foo-bar'. Handle nu ('foo-bar') é interpretado como
    /in/<handle> (mapeamento fixo e documentado, não heurística fuzzy).
    """
    if raw is None:
        return None
    v = raw.strip().lower()
    if not v:
        return None
    if "://" not in v:
        v = "//" + v  # urlsplit trata como netloc+path
    parts = urlsplit(v)
    host = (parts.netloc or "").split(":")[0]
    path = (parts.path or "").strip("/")
    if host and not (host == "linkedin.com" or host.endswith(".linkedin.com")):
        # não é linkedin: o "host" era na verdade o início de um handle/caminho
        path = f"{host}/{path}".strip("/") if path else host
    if not path:
        return None
    if "/" not in path:
        path = f"in/{path}"
    return path


@dataclass
class PersonResolution:
    identity: Optional[CrmPersonIdentity]
    created: bool = False
    conflict: bool = False
    matched: list[CrmPersonIdentity] = field(default_factory=list)


def resolve_person(
    session: Session,
    tenant_id: uuid.UUID,
    email_raw: Optional[str],
    linkedin_raw: Optional[str],
    display_name: Optional[str] = None,
) -> PersonResolution:
    """Resolve (ou cria) a identidade da pessoa por igualdade exata das chaves."""
    email = normalize_email(email_raw)
    linkedin = normalize_linkedin(linkedin_raw)
    if email is None and linkedin is None:
        return PersonResolution(identity=None)

    by_email = (
        session.query(CrmPersonIdentity)
        .filter(
            CrmPersonIdentity.tenant_id == tenant_id,
            CrmPersonIdentity.email_normalized == email,
        )
        .one_or_none()
        if email
        else None
    )
    by_linkedin = (
        session.query(CrmPersonIdentity)
        .filter(
            CrmPersonIdentity.tenant_id == tenant_id,
            CrmPersonIdentity.linkedin_normalized == linkedin,
        )
        .one_or_none()
        if linkedin
        else None
    )

    if by_email is not None and by_linkedin is not None and by_email.id != by_linkedin.id:  # type: ignore[misc]
        # Chaves apontam para pessoas diferentes: conflito. Sem merge silencioso.
        return PersonResolution(identity=None, conflict=True, matched=[by_email, by_linkedin])

    found = by_email or by_linkedin
    if found is not None:
        # Enriquecimento determinístico: só preenche chave vazia; nunca sobrescreve.
        if email and found.email_normalized is None and by_email is None:
            found.email_normalized = email  # type: ignore[assignment]
        if linkedin and found.linkedin_normalized is None and by_linkedin is None:
            found.linkedin_normalized = linkedin  # type: ignore[assignment]
        if display_name and found.display_name is None:
            found.display_name = display_name  # type: ignore[assignment]
        return PersonResolution(identity=found, matched=[found])

    identity = CrmPersonIdentity(
        tenant_id=tenant_id,
        email_normalized=email,
        linkedin_normalized=linkedin,
        display_name=display_name,
    )
    session.add(identity)
    session.flush()
    return PersonResolution(identity=identity, created=True, matched=[identity])


def person_protected(
    session: Session, tenant_id: uuid.UUID, identity_ids: list[uuid.UUID]
) -> bool:
    """True se QUALQUER vínculo da(s) pessoa(s) está em estado protegido.

    É o coração da DEC-5: a consulta cruza por person_identity_id, então um novo
    external_lead_id da mesma pessoa herda a proteção existente. Em conflito de
    identidade, o chamador passa TODAS as identidades candidatas — proteger a
    mais é o modo de falha correto (fail-safe), desproteger jamais.
    """
    if not identity_ids:
        return False
    return session.query(
        session.query(CrmLeadLink)
        .filter(
            CrmLeadLink.tenant_id == tenant_id,
            CrmLeadLink.person_identity_id.in_(identity_ids),
            CrmLeadLink.ownership_state.in_(PROTECTED_OWNERSHIP_STATES),
        )
        .exists()
    ).scalar()
