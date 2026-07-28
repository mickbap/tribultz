"""Deduplicação por domínio de e-mail entre CNPJ básicos distintos
(PO-2026-07-SALES-001, Fase 1).

A consolidação por CNPJ básico (matriz+filiais) já garante que nunca existam
dois registros para o mesmo CNPJ básico — isso é trivial e acontece em
consolidation.py. O caso difícil, tratado aqui, é: dois CNPJ básicos
DIFERENTES que na prática são o mesmo escritório (várias inscrições para
linhas de serviço/filiais separadas, todas sob o mesmo domínio de e-mail).

Regra (decisão de design documentada — a PO não especifica o critério exato):
- Só domínio "dominio_nominal" (derivado do nome da própria empresa) participa
  do agrupamento. Domínio gratuito (gmail etc.) nunca deduplica por coincidência
  — dois escritórios não relacionados compartilhando @gmail.com é coincidência,
  não evidência de serem a mesma empresa.
- Grupo de 2 até --max-group-size (padrão 5): mescla, mantendo o "primário"
  (mais estabelecimentos -> maior capital social -> menor cnpj_basico,
  determinístico e reproduzível) e marcando os demais como 'merged' (nunca
  apagados — a origem RF é preservada para auditoria).
- Grupo maior que --max-group-size: mais provável ser plataforma/hospedagem
  white-label do que uma única firma — não mescla, mantém todos 'unique'.

Idempotente: cada execução reseta dedup_status/merged_into_id de TODOS os
registros e recalcula os grupos do zero a partir do estado atual da tabela —
por isso é seguro rodar de novo a qualquer momento (ex.: após um novo ingest).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.prospect_org import ProspectOrg

DEFAULT_MAX_GROUP_SIZE = 5


@dataclass(frozen=True)
class DedupSummary:
    groups_merged: int
    orgs_merged: int
    domains_skipped_too_large: int


def _pick_primary(members: list[ProspectOrg]) -> ProspectOrg:
    """Desempate determinístico: mais estabelecimentos -> maior capital social
    -> menor cnpj_basico."""
    return sorted(
        members,
        key=lambda o: (
            -cast(int, o.qtd_estabelecimentos),
            -float(cast(Decimal, o.capital_social)),
            cast(str, o.cnpj_basico),
        ),
    )[0]


def apply_dedup(db: Session, max_group_size: int = DEFAULT_MAX_GROUP_SIZE) -> DedupSummary:
    """Recalcula do zero o agrupamento por domínio nominal e aplica dedup_status/
    merged_into_id. Faz commit ao final."""
    # dedup_status é um cache mutável (não append-only) — reset garante que
    # reprocessar reflita o estado atual da tabela, não decisões de execuções passadas.
    db.execute(update(ProspectOrg).values(dedup_status="unique", merged_into_id=None))
    db.flush()

    candidates = db.execute(
        select(ProspectOrg).where(ProspectOrg.email_domain_category == "dominio_nominal")
    ).scalars().all()

    groups: dict[str, list[ProspectOrg]] = defaultdict(list)
    for org in candidates:
        email_domain = cast("str | None", org.email_domain)
        if email_domain:
            groups[email_domain].append(org)

    groups_merged = 0
    orgs_merged = 0
    domains_skipped_too_large = 0

    for members in groups.values():
        if len(members) < 2:
            continue
        if len(members) > max_group_size:
            domains_skipped_too_large += 1
            continue

        primary = _pick_primary(members)
        primary.dedup_status = "primary"  # type: ignore[assignment]
        primary_id = cast("object", primary.id)
        for member in members:
            if cast("object", member.id) == primary_id:
                continue
            member.dedup_status = "merged"  # type: ignore[assignment]
            member.merged_into_id = primary.id  # type: ignore[assignment]
            orgs_merged += 1
        groups_merged += 1

    db.commit()
    return DedupSummary(
        groups_merged=groups_merged,
        orgs_merged=orgs_merged,
        domains_skipped_too_large=domains_skipped_too_large,
    )
