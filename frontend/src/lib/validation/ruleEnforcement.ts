import type { RuleEnforcementState, XmlDocumentType } from "@/lib/types";

type Milestone = { value: boolean; effectiveFrom?: string };
type Lifecycle = {
  documentType: XmlDocumentType;
  ruleId: string;
  version: string;
  legalRequired: Milestone;
  schemaSupported: Milestone;
  validationRuleDefined: Milestone;
  homologationEnforced: Milestone;
  productionEnforced: Milestone;
};

const knownWithoutRecordedStart: Milestone = { value: true };

const lifecycles: readonly Lifecycle[] = [
  {
    documentType: "NFE",
    ruleId: "DANFE_SIMPLIFICADO_RESTRICAO",
    version: "1.00",
    legalRequired: { value: true, effectiveFrom: "2026-08-03" },
    schemaSupported: knownWithoutRecordedStart,
    validationRuleDefined: knownWithoutRecordedStart,
    homologationEnforced: knownWithoutRecordedStart,
    productionEnforced: { value: true, effectiveFrom: "2026-08-03" },
  },
  {
    documentType: "NFE",
    ruleId: "DANFE_SIMPLIFICADO_CFOP",
    version: "1.10a",
    legalRequired: { value: true, effectiveFrom: "2026-08-03" },
    schemaSupported: knownWithoutRecordedStart,
    validationRuleDefined: knownWithoutRecordedStart,
    homologationEnforced: knownWithoutRecordedStart,
    productionEnforced: { value: true, effectiveFrom: "2026-08-03" },
  },
];

function activeAt(milestone: Milestone, asOf: string): boolean {
  return milestone.value && (!milestone.effectiveFrom || asOf >= milestone.effectiveFrom);
}

function isIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

export const RULE_VERSION_BY_KEY: Readonly<Record<string, string>> = Object.fromEntries(
  lifecycles.map((item) => [`${item.documentType}:${item.ruleId}`, item.version]),
);

export function resolveRuleEnforcement(
  documentType: XmlDocumentType,
  ruleId: string,
  version: string,
  asOf: string,
): RuleEnforcementState | undefined {
  if (!isIsoDate(asOf)) return undefined;
  const lifecycle = lifecycles.find(
    (item) => item.documentType === documentType && item.ruleId === ruleId && item.version === version,
  );
  if (!lifecycle) return undefined;

  return {
    document_type: lifecycle.documentType,
    rule_id: lifecycle.ruleId,
    version: lifecycle.version,
    as_of: asOf,
    legal_required: activeAt(lifecycle.legalRequired, asOf),
    schema_supported: activeAt(lifecycle.schemaSupported, asOf),
    validation_rule_defined: activeAt(lifecycle.validationRuleDefined, asOf),
    homologation_enforced: activeAt(lifecycle.homologationEnforced, asOf),
    production_enforced: activeAt(lifecycle.productionEnforced, asOf),
    effective_from: {
      legal_required: lifecycle.legalRequired.effectiveFrom ?? null,
      schema_supported: lifecycle.schemaSupported.effectiveFrom ?? null,
      validation_rule_defined: lifecycle.validationRuleDefined.effectiveFrom ?? null,
      homologation_enforced: lifecycle.homologationEnforced.effectiveFrom ?? null,
      production_enforced: lifecycle.productionEnforced.effectiveFrom ?? null,
    },
  };
}
