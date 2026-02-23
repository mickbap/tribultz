export type EvidenceType = "job" | "audit" | "file" | "link";

export type Evidence = {
  type: EvidenceType;
  job_id?: string;
  audit_id?: string;
  href: string;
  label: string;
  payload?: Record<string, unknown> | null;
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
      const type = typeof row.type === "string" ? row.type : "link";
      return {
        type: (type === "job" || type === "audit" || type === "file" || type === "link" ? type : "link") as EvidenceType,
        job_id: typeof row.job_id === "string" ? row.job_id : undefined,
        audit_id: typeof row.audit_id === "string" ? row.audit_id : undefined,
        href: typeof row.href === "string" ? row.href : "#",
        label: typeof row.label === "string" ? row.label : "Evidence",
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

