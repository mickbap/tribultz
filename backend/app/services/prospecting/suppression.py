"""Filtro contra a lista de supressão (PO-2026-07-SALES-001, Fase 1).

Semântica de exclusão (decisão de design documentada — a PO define os status
mas não qual é obrigatório vs. configurável):
- opt_out/cliente: exclusão dura, incondicional, sem flag de CLI para
  desativar — "nunca poderão reaparecer", literal da PO.
- lead_ativo/desqualificado: excluídos por padrão (uma lista de prospecção nova
  não deveria trazer de volta um CNPJ que o comercial já tem em negociação
  ativa, ou que já foi avaliado e rejeitado), mas configurável via
  --suppress-statuses.
- hard_bounce: NÃO excluído por padrão — um e-mail que bateu hoje não
  desqualifica a FIRMA; um contato corrigido pode aparecer no enriquecimento
  da Fase 2. Operador pode incluir explicitamente se quiser.

Casamento por cnpj_basico OU email_domain (a tabela de supressão não exige as
duas colunas — ver CheckConstraint no model).
"""

from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.prospect_org import ProspectOrg
from app.models.prospect_suppression import ProspectSuppression

MANDATORY_EXCLUDE_STATUSES: frozenset[str] = frozenset({"opt_out", "cliente"})
DEFAULT_EXCLUDE_STATUSES: frozenset[str] = frozenset(
    {"opt_out", "cliente", "lead_ativo", "desqualificado"}
)


def get_suppressed_keys(
    db: Session, exclude_statuses: frozenset[str] = DEFAULT_EXCLUDE_STATUSES
) -> tuple[set[str], set[str]]:
    """Retorna (cnpj_basicos, email_domains) suprimidos para os status pedidos.

    MANDATORY_EXCLUDE_STATUSES é sempre incluído, mesmo que o chamador não o
    peça explicitamente — não há como desativar opt_out/cliente.
    """
    statuses = MANDATORY_EXCLUDE_STATUSES | exclude_statuses
    rows = db.execute(
        select(ProspectSuppression).where(ProspectSuppression.status.in_(statuses))
    ).scalars().all()
    cnpjs = {cast(str, r.cnpj_basico) for r in rows if cast("str | None", r.cnpj_basico)}
    domains = {cast(str, r.email_domain) for r in rows if cast("str | None", r.email_domain)}
    return cnpjs, domains


def is_suppressed(
    org: ProspectOrg, suppressed_cnpjs: set[str], suppressed_domains: set[str]
) -> bool:
    if cast(str, org.cnpj_basico) in suppressed_cnpjs:
        return True
    email_domain = cast("str | None", org.email_domain)
    if email_domain and email_domain in suppressed_domains:
        return True
    return False


def filter_candidates(
    db: Session,
    candidates: list[ProspectOrg],
    exclude_statuses: frozenset[str] = DEFAULT_EXCLUDE_STATUSES,
) -> list[ProspectOrg]:
    """Remove candidatos suprimidos. exclude_statuses controla só a parte
    configurável — opt_out/cliente são sempre aplicados, ver MANDATORY_EXCLUDE_STATUSES."""
    suppressed_cnpjs, suppressed_domains = get_suppressed_keys(db, exclude_statuses)
    return [
        org for org in candidates
        if not is_suppressed(org, suppressed_cnpjs, suppressed_domains)
    ]
