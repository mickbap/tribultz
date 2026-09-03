"""Estados independentes de disponibilidade e enforcement de regras de DF-e.

O registro e deliberadamente pequeno: ele descreve apenas regras que o motor ja
implementa. A ausencia de uma entrada significa "estado nao catalogado", nunca
"nao vigente". Novos tipos documentais nao devem ser adicionados aqui antes de
existir suporte funcional no validador.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class StateMilestone:
    value: bool
    effective_from: date | None = None

    def at(self, as_of: date) -> bool:
        return self.value and (self.effective_from is None or as_of >= self.effective_from)


@dataclass(frozen=True)
class RuleLifecycle:
    document_type: str
    rule_id: str
    version: str
    legal_required: StateMilestone
    schema_supported: StateMilestone
    validation_rule_defined: StateMilestone
    homologation_enforced: StateMilestone
    production_enforced: StateMilestone


_KNOWN_WITHOUT_RECORDED_START = StateMilestone(True)

# NT 2026.002: somente NF-e modelo 55. A data de producao e o marco ja usado
# pelo motor para severidade. Schema/RV/homologacao sao conhecidos como ativos,
# mas o repositorio nao guarda seus marcos oficiais; por isso eles nao recebem
# uma data inventada.
_RULE_LIFECYCLES: tuple[RuleLifecycle, ...] = (
    RuleLifecycle(
        document_type="NFE",
        rule_id="DANFE_SIMPLIFICADO_RESTRICAO",
        version="1.00",
        legal_required=StateMilestone(True, date(2026, 8, 3)),
        schema_supported=_KNOWN_WITHOUT_RECORDED_START,
        validation_rule_defined=_KNOWN_WITHOUT_RECORDED_START,
        homologation_enforced=_KNOWN_WITHOUT_RECORDED_START,
        production_enforced=StateMilestone(True, date(2026, 8, 3)),
    ),
    RuleLifecycle(
        document_type="NFE",
        rule_id="DANFE_SIMPLIFICADO_CFOP",
        version="1.10a",
        legal_required=StateMilestone(True, date(2026, 8, 3)),
        schema_supported=_KNOWN_WITHOUT_RECORDED_START,
        validation_rule_defined=_KNOWN_WITHOUT_RECORDED_START,
        homologation_enforced=_KNOWN_WITHOUT_RECORDED_START,
        production_enforced=StateMilestone(True, date(2026, 8, 3)),
    ),
)


def resolve_rule_enforcement(
    document_type: str,
    rule_id: str,
    version: str,
    as_of: date,
) -> dict[str, str | bool | None] | None:
    """Resolve um estado exato; nao faz fallback entre documento ou versao."""
    lifecycle = next(
        (
            item
            for item in _RULE_LIFECYCLES
            if item.document_type == document_type
            and item.rule_id == rule_id
            and item.version == version
        ),
        None,
    )
    if lifecycle is None:
        return None

    def effective(milestone: StateMilestone) -> str | None:
        return milestone.effective_from.isoformat() if milestone.effective_from else None

    return {
        "document_type": lifecycle.document_type,
        "rule_id": lifecycle.rule_id,
        "version": lifecycle.version,
        "as_of": as_of.isoformat(),
        "legal_required": lifecycle.legal_required.at(as_of),
        "schema_supported": lifecycle.schema_supported.at(as_of),
        "validation_rule_defined": lifecycle.validation_rule_defined.at(as_of),
        "homologation_enforced": lifecycle.homologation_enforced.at(as_of),
        "production_enforced": lifecycle.production_enforced.at(as_of),
        "effective_from": {
            "legal_required": effective(lifecycle.legal_required),
            "schema_supported": effective(lifecycle.schema_supported),
            "validation_rule_defined": effective(lifecycle.validation_rule_defined),
            "homologation_enforced": effective(lifecycle.homologation_enforced),
            "production_enforced": effective(lifecycle.production_enforced),
        },
    }


RULE_VERSION_BY_KEY = {
    (item.document_type, item.rule_id): item.version for item in _RULE_LIFECYCLES
}
