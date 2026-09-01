"""Gates fail-closed e dry-run de ativação por e-mail com Resend (#733).

Este módulo não envia e-mail nem chama o Resend. Ele transforma a decisão
explícita registrada no domínio em uma lista auditável de quem *poderia* ser
sincronizado numa etapa posterior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crm_handoff import CrmLeadLink, CrmPersonIdentity
from app.models.prospect_org import ProspectOrg
from app.models.prospect_suppression import ProspectSuppression


class MarketingState(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    SUPPRESSED = "SUPPRESSED"


@dataclass(frozen=True)
class MarketingDecision:
    state: MarketingState
    reason: str
    human_controlled: bool = False


@dataclass(frozen=True)
class SuppressionIndex:
    cnpjs: frozenset[str]
    emails: frozenset[str]
    domains: frozenset[str]


@dataclass(frozen=True)
class DryRunSummary:
    TOTAL_BASE: int
    ELIGIBLE: int
    INELIGIBLE: int
    SUPPRESSED: int
    CONTROLE_HUMANO: int
    TOTAL_ENVIAVEL: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def normalize_email(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    return normalized or None


def _has_minimum_provenance(org: ProspectOrg) -> bool:
    return all(
        (
            cast("str | None", org.marketing_origin),
            cast("str | None", org.marketing_purpose),
            cast("str | None", org.marketing_legal_basis),
        )
    )


def _is_explicitly_eligible(org: ProspectOrg) -> bool:
    return (
        cast(str, org.marketing_eligibility) == MarketingState.ELIGIBLE
        and normalize_email(cast("str | None", org.email)) is not None
        and cast(str, org.dedup_status) != "merged"
        and _has_minimum_provenance(org)
    )


def build_suppression_index(rows: list[ProspectSuppression]) -> SuppressionIndex:
    return SuppressionIndex(
        cnpjs=frozenset(
            value for row in rows if (value := cast("str | None", row.cnpj_basico))
        ),
        emails=frozenset(
            value
            for row in rows
            if (value := normalize_email(cast("str | None", row.email)))
        ),
        domains=frozenset(
            value.lower()
            for row in rows
            if (value := cast("str | None", row.email_domain))
        ),
    )


def _suppression_matches(org: ProspectOrg, suppression: SuppressionIndex) -> bool:
    org_email = normalize_email(cast("str | None", org.email))
    if org_email and org_email in suppression.emails:
        return True
    org_cnpj = cast(str, org.cnpj_basico)
    if org_cnpj in suppression.cnpjs:
        return True
    org_domain = cast("str | None", org.email_domain)
    return bool(org_domain and org_domain.lower() in suppression.domains)


def decide_marketing_state(
    org: ProspectOrg,
    suppressions: list[ProspectSuppression] | SuppressionIndex,
    human_controlled_emails: set[str],
) -> MarketingDecision:
    """Aplica elegibilidade → controle humano/suppression, nesta ordem lógica."""
    if not _is_explicitly_eligible(org):
        return MarketingDecision(MarketingState.INELIGIBLE, "ELIGIBILIDADE_OU_PROVENANCE_INCOMPLETA")

    email = normalize_email(cast("str | None", org.email))
    assert email is not None  # garantido pelo gate acima
    if email in human_controlled_emails:
        return MarketingDecision(MarketingState.SUPPRESSED, "CONTROLE_HUMANO", True)
    suppression_index = (
        suppressions
        if isinstance(suppressions, SuppressionIndex)
        else build_suppression_index(suppressions)
    )
    if _suppression_matches(org, suppression_index):
        return MarketingDecision(MarketingState.SUPPRESSED, "SUPPRESSION_TRIBULTZ")
    return MarketingDecision(MarketingState.ELIGIBLE, "APTO_PARA_DRY_RUN")


def get_human_controlled_emails(db: Session) -> set[str]:
    """Pessoa fora de automação ou sob handoff/humano nunca entra no outbound."""
    rows = db.execute(
        select(CrmPersonIdentity.email_normalized)
        .join(CrmLeadLink, CrmLeadLink.person_identity_id == CrmPersonIdentity.id)
        .where(
            CrmPersonIdentity.email_normalized.is_not(None),
            (
                CrmLeadLink.ownership_state.in_(("HANDOFF_REQUESTED", "HUMAN_OWNED"))
                | (CrmLeadLink.automation_state != "ACTIVE")
                | CrmLeadLink.identity_conflict.is_(True)
            ),
        )
    ).scalars()
    return {email for raw in rows if (email := normalize_email(raw))}


def build_dry_run(db: Session) -> DryRunSummary:
    """Calcula os seis números do P0; não escreve nem acessa o provedor.

    ELIGIBLE é a população com decisão/provenance válida antes dos bloqueios.
    SUPPRESSED inclui controle humano; CONTROLE_HUMANO é seu subconjunto
    explicativo. Assim TOTAL_ENVIAVEL = ELIGIBLE - SUPPRESSED.
    """
    orgs = list(db.execute(select(ProspectOrg)).scalars())
    suppressions = build_suppression_index(
        list(db.execute(select(ProspectSuppression)).scalars())
    )
    human_emails = get_human_controlled_emails(db)

    eligible = 0
    ineligible = 0
    suppressed = 0
    human_controlled = 0
    sendable = 0
    for org in orgs:
        decision = decide_marketing_state(org, suppressions, human_emails)
        if decision.state == MarketingState.INELIGIBLE:
            ineligible += 1
            continue
        eligible += 1
        if decision.state == MarketingState.SUPPRESSED:
            suppressed += 1
            human_controlled += int(decision.human_controlled)
        else:
            sendable += 1

    return DryRunSummary(
        TOTAL_BASE=len(orgs),
        ELIGIBLE=eligible,
        INELIGIBLE=ineligible,
        SUPPRESSED=suppressed,
        CONTROLE_HUMANO=human_controlled,
        TOTAL_ENVIAVEL=sendable,
    )
