export type XmlDocumentType = "NFSE" | "NFE" | "NFCE";

export type EvidenceType = "xml" | "link" | "print" | "job" | "audit" | "file";

export type Evidence = {
  id?: string;
  type: EvidenceType;
  job_id?: string;
  audit_id?: string;
  href?: string;
  label: string;
  xpath?: string;
  snippet?: string;
  payload?: Record<string, unknown> | null;
};

export type FindingSeverity = "FATAL" | "ALERT" | "WARNING";

export type FindingWhere = {
  field?: string;
  xpath?: string;
  snippet?: string;
};

export type FiscalJustification = {
  base_legal: string;
  explicacao: string;
  correcao: string;
};

export type RuleEnforcementState = {
  document_type: XmlDocumentType;
  rule_id: string;
  version: string;
  as_of: string;
  legal_required: boolean;
  schema_supported: boolean;
  validation_rule_defined: boolean;
  homologation_enforced: boolean;
  production_enforced: boolean;
  effective_from: Record<
    "legal_required" | "schema_supported" | "validation_rule_defined" |
    "homologation_enforced" | "production_enforced",
    string | null
  >;
};

export type Finding = {
  id: string;
  severity: FindingSeverity;
  rule_id: string;
  title: string;
  where: FindingWhere;
  recommendation: string;
  evidence_ids: string[];
  /** Estados independentes da regra na data do documento, quando catalogados. */
  enforcement?: RuleEnforcementState;
  /** Justificativa técnica — presente apenas em planos Profissional/Empresarial/Contador */
  justification?: FiscalJustification;
  /** true quando há justificativa mas o plano atual não tem acesso */
  justification_gated?: boolean;
};

export type ValidationEvidence = {
  id: string;
  type: "xml" | "link" | "print" | "job" | "audit";
  label: string;
  href?: string;
  xpath?: string;
  snippet?: string;
};

export type ValidationJobRef = {
  id: string;
  created_at: string;
  tenant_id: string;
  transaction_id?: string;
};

export type ValidationAuditEvent = {
  id: string;
  action: string;
  created_at: string;
  payload: Record<string, unknown>;
};

export type ValidationAuditRef = {
  id: string;
  job_id: string;
  events: ValidationAuditEvent[];
};

export type ValidationResultV11 = {
  job: ValidationJobRef;
  audit: ValidationAuditRef;
  findings: Finding[];
  evidences: ValidationEvidence[];
  transaction_id?: string;
};

export type ExceptionRequestStatus = "OPEN" | "APPROVED" | "REJECTED";

export type ExceptionRequest = {
  id: string;
  tenant_id: string;
  job_id: string;
  finding_id: string;
  rule_id: string;
  justification: string;
  status: ExceptionRequestStatus;
  admin_name: string;
  admin_email: string;
  created_by: string;
  created_at: string;
  decided_by?: string;
  decided_at?: string;
  decision_comment?: string;
};

export type ExceptionDecision = {
  status: "APPROVED" | "REJECTED";
  decision_comment?: string;
  decided_by: string;
};

export type ValidateXmlRequest = {
  document_type: XmlDocumentType;
  xml: string;
  source?: "paste" | "upload";
  transaction_id?: string;
};

export type JobStatus = "QUEUED" | "RUNNING" | "SUCCESS" | "FAILED";

export type Job = {
  id: string;
  tenantId: string;
  jobType: string;
  status: JobStatus;
  createdAt: string;
  updatedAt: string;
  input: Record<string, unknown>;
  output?: Record<string, unknown> | null;
  reportMarkdown?: string | null;
  evidence: Evidence[];
  findings?: Finding[];
  exceptionRequests?: ExceptionRequest[];
};

export type AuditLog = {
  id: string;
  tenantId: string;
  jobId?: string;
  action: string;
  createdAt: string;
  payload: Record<string, unknown>;
};

export type ApiJob = {
  id: string;
  tenant_id?: string;
  tenantId?: string;
  job_type?: string;
  jobType?: string;
  status: string;
  created_at?: string;
  createdAt?: string;
  updated_at?: string;
  updatedAt?: string;
  input_data?: Record<string, unknown>;
  input?: Record<string, unknown>;
  payload?: Record<string, unknown>;
  output_data?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  report_markdown?: string | null;
  reportMarkdown?: string | null;
  evidence?: Evidence[];
  findings?: Finding[];
};

export type ApiAudit = {
  id: string;
  tenant_id?: string;
  tenantId?: string;
  job_id?: string;
  jobId?: string;
  action: string;
  created_at?: string;
  createdAt?: string;
  payload?: Record<string, unknown>;
};

export type ApiExceptionRequest = {
  id: string;
  tenant_id?: string;
  job_id: string;
  finding_id: string;
  rule_id: string;
  justification: string;
  status: ExceptionRequestStatus;
  admin_name?: string;
  admin_email?: string;
  created_by: string;
  created_at: string;
  decided_by?: string;
  decided_at?: string;
  decision_comment?: string;
};

function toIsoOrNow(value?: string): string {
  if (!value) return new Date().toISOString();
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return new Date().toISOString();
  return d.toISOString();
}

function asEvidenceList(raw: unknown): Evidence[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item) => item && typeof item === "object")
    .map((item) => {
      const row = item as Record<string, unknown>;
      const type = typeof row.type === "string" ? row.type.toLowerCase() : "link";
      const normalizedType: EvidenceType =
        type === "xml" || type === "link" || type === "print" || type === "job" || type === "audit" || type === "file"
          ? (type as EvidenceType)
          : "link";
      return {
        id: typeof row.id === "string" ? row.id : undefined,
        type: normalizedType,
        job_id: typeof row.job_id === "string" ? row.job_id : undefined,
        audit_id: typeof row.audit_id === "string" ? row.audit_id : undefined,
        href: typeof row.href === "string" ? row.href : undefined,
        label: typeof row.label === "string" ? row.label : "Evidence",
        xpath: typeof row.xpath === "string" ? row.xpath : undefined,
        snippet: typeof row.snippet === "string" ? row.snippet : undefined,
        payload: row.payload && typeof row.payload === "object" ? (row.payload as Record<string, unknown>) : null,
      };
    });
}

export function normalizeJob(raw: ApiJob, fallbackTenant: string): Job {
  const evidence = asEvidenceList(raw.evidence);
  const statusUpper = String(raw.status ?? "QUEUED").toUpperCase();
  return {
    id: raw.id,
    tenantId: raw.tenantId ?? raw.tenant_id ?? fallbackTenant,
    jobType: raw.jobType ?? raw.job_type ?? "unknown_job",
    status: (statusUpper === "QUEUED" || statusUpper === "RUNNING" || statusUpper === "SUCCESS" || statusUpper === "FAILED"
      ? statusUpper
      : "QUEUED") as JobStatus,
    createdAt: toIsoOrNow(raw.createdAt ?? raw.created_at),
    updatedAt: toIsoOrNow(raw.updatedAt ?? raw.updated_at),
    input: raw.input ?? raw.input_data ?? raw.payload ?? {},
    output: raw.output ?? raw.output_data ?? raw.result ?? null,
    reportMarkdown: raw.reportMarkdown ?? raw.report_markdown ?? null,
    evidence,
    // findings at top level (enriched by server) takes priority; fallback to output.findings or result.findings
    findings: Array.isArray(raw.findings) && raw.findings.length
      ? (raw.findings as Finding[])
      : Array.isArray((raw.output as Record<string, unknown> | null)?.findings)
        ? ((raw.output as Record<string, unknown>).findings as Finding[])
        : Array.isArray((raw.result as Record<string, unknown> | null)?.findings)
          ? ((raw.result as Record<string, unknown>).findings as Finding[])
          : undefined,
  };
}

export function normalizeAudit(raw: ApiAudit, fallbackTenant: string): AuditLog {
  return {
    id: raw.id,
    tenantId: raw.tenantId ?? raw.tenant_id ?? fallbackTenant,
    jobId: raw.jobId ?? raw.job_id,
    action: raw.action,
    createdAt: toIsoOrNow(raw.createdAt ?? raw.created_at),
    payload: raw.payload ?? {},
  };
}

export function normalizeException(raw: ApiExceptionRequest, fallbackTenant: string): ExceptionRequest {
  return {
    id: raw.id,
    tenant_id: raw.tenant_id ?? fallbackTenant,
    job_id: raw.job_id,
    finding_id: raw.finding_id,
    rule_id: raw.rule_id,
    justification: raw.justification,
    status: raw.status,
    admin_name: raw.admin_name ?? "",
    admin_email: raw.admin_email ?? "",
    created_by: raw.created_by,
    created_at: raw.created_at,
    decided_by: raw.decided_by,
    decided_at: raw.decided_at,
    decision_comment: raw.decision_comment,
  };
}
