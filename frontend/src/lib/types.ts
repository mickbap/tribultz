export type XmlDocumentType = "NFSE" | "NFE";

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

export type FindingSeverity = "FATAL" | "ALERT";

export type FindingWhere = {
  field?: string;
  xpath?: string;
  snippet?: string;
};

export type Finding = {
  id: string;
  severity: FindingSeverity;
  rule_id: string;
  title: string;
  where: FindingWhere;
  recommendation: string;
  evidence_ids: string[];
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
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  markdown: string;
  createdAt: string;
  evidence?: Evidence[];
};

export type Conversation = {
  id: string;
  title: string;
  updatedAt: string;
  messages: ChatMessage[];
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

export type ChatRequest = {
  message: string;
  conversation_id?: string | null;
};

export type ChatResponseA = {
  conversation_id: string;
  assistant_markdown?: string;
  response_markdown?: string;
  evidence?: Evidence[];
};

export type ChatResponseB = {
  conversation_id: string;
  assistant_markdown?: string;
  response_markdown?: string;
  job_id?: string;
  job_href?: string;
  evidence?: Evidence[];
};

export type ChatApiResponse = ChatResponseA | ChatResponseB;

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
  output_data?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
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
  created_by: string;
  created_at: string;
  decided_by?: string;
  decided_at?: string;
  decision_comment?: string;
};

export type NormalizedChatResponse = {
  conversationId: string;
  assistantMarkdown: string;
  evidence: Evidence[];
  job?: {
    id: string;
    href: string;
  };
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

export function normalizeChatResponse(raw: ChatApiResponse): NormalizedChatResponse {
  const assistantMarkdown = raw.assistant_markdown ?? raw.response_markdown ?? "";
  const evidence = asEvidenceList(raw.evidence);

  const jobFromEvidence = evidence.find((item) => item.type === "job" && item.job_id && item.href);
  const rawJobId = "job_id" in raw ? raw.job_id : undefined;
  const rawJobHref = "job_href" in raw ? raw.job_href : undefined;
  const jobId = rawJobId ?? jobFromEvidence?.job_id;
  const jobHref = rawJobHref ?? jobFromEvidence?.href;

  if (jobId && jobHref && !jobFromEvidence) {
    evidence.unshift({
      type: "job",
      job_id: jobId,
      href: jobHref,
      label: "Job de validação",
    });
  }

  return {
    conversationId: raw.conversation_id,
    assistantMarkdown,
    evidence,
    job: jobId && jobHref ? { id: jobId, href: jobHref } : undefined,
  };
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
    input: raw.input ?? raw.input_data ?? {},
    output: raw.output ?? raw.output_data ?? null,
    reportMarkdown: raw.reportMarkdown ?? raw.report_markdown ?? null,
    evidence,
    findings: Array.isArray(raw.findings) ? raw.findings : undefined,
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
    created_by: raw.created_by,
    created_at: raw.created_at,
    decided_by: raw.decided_by,
    decided_at: raw.decided_at,
    decision_comment: raw.decision_comment,
  };
}
