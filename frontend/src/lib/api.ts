import {
  ApiAudit,
  ApiExceptionRequest,
  ApiJob,
  AuditLog,
  ExceptionDecision,
  ExceptionRequest,
  Job,
  ValidateXmlRequest,
  ValidationResultV11,
  normalizeAudit,
  normalizeException,
  normalizeJob,
} from "./types";
import { makeJobEvidenceZipFilename } from "./export/jobEvidenceZip";
import { getTenantId, getToken } from "./storage";

// Use || (not ??) so empty-string env vars also fall back to localhost.
// If NEXT_PUBLIC_API_BASE_URL="" the fetch URL becomes relative ("/api/...")
// which hits the Next.js server itself and returns 404.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function createTransactionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `txn-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

type LoginRequest = {
  email: string;
  password: string;
  tenant_slug: string;
  captcha_token?: string;
};

type TenantInfo = {
  id: string;
  name: string;
  slug: string;
  is_default: boolean;
};

type LoginResponse = {
  access_token: string;
  token_type?: string;
  tenant_id?: string;
  account_type?: string;
  plan_slug?: string;
  role?: string;
  tenants?: TenantInfo[];
};

type RegisterRequest = {
  email: string;
  password: string;
  full_name: string;
  cnpj: string;
  phone: string;
  account_type: string;
  plan_slug: string;
  billing_type: string;
  lgpd_consent: boolean;
  tenant_slug: string;
  captcha_token?: string;
};

type RegisterResponse = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  tenant_id: string;
  is_active: boolean;
  plan_slug?: string;
  subscription_status?: string;
  checkout_url?: string;
  pix_qr_code?: string;
  pix_copy_paste?: string;
};

export type JobEvidenceZipResult = {
  filename: string;
  bytes: Uint8Array;
};

function headers(extra?: HeadersInit, transactionId?: string): HeadersInit {
  const token = getToken();
  const tenant = getTenantId();
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    "X-Tenant-Id": tenant,
    ...(transactionId ? { "X-Transaction-Id": transactionId } : {}),
    ...(extra ?? {}),
  };
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  options?: { transactionId?: string },
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: headers(init.headers, options?.transactionId),
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "Erro de API");
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export async function loginWithApi(payload: LoginRequest): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-Id": payload.tenant_slug,
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Erro ao autenticar" }));
    throw new Error(body.detail ?? `Login ${res.status}`);
  }
  return (await res.json()) as LoginResponse;
}

export async function resendVerificationEmail(payload: LoginRequest): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/auth/resend-verification`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-Id": payload.tenant_slug,
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Erro ao reenviar" }));
    throw new Error(body.detail ?? `Resend ${res.status}`);
  }
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/api/v1/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Erro ao solicitar" }));
    throw new Error(body.detail ?? `Erro ${res.status}`);
  }
  return (await res.json()) as { message: string };
}

export async function resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/api/v1/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Erro ao redefinir" }));
    throw new Error(body.detail ?? `Erro ${res.status}`);
  }
  return (await res.json()) as { message: string };
}

export async function registerWithApi(payload: RegisterRequest): Promise<RegisterResponse> {
  const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-Id": payload.tenant_slug,
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "Erro ao registrar");
    throw new Error(`Registro ${res.status}: ${detail}`);
  }
  return (await res.json()) as RegisterResponse;
}

type ValidationResultApi = {
  job_id?: string;
  audit_id?: string;
  document_type?: string;
  findings?: ValidationResultV11["findings"];
  evidences?: ValidationResultV11["evidences"];
  fatals?: number;
  alerts?: number;
  created_at?: string;
  job?: ValidationResultV11["job"];
  audit?: ValidationResultV11["audit"];
  transaction_id?: string;
};

export function adaptValidationResult(
  raw: ValidationResultApi,
  tenantId: string,
  transactionId: string,
): ValidationResultV11 {
  const createdAt = raw.created_at ?? raw.job?.created_at ?? new Date().toISOString();
  const jobId = raw.job?.id ?? raw.job_id ?? "";
  const auditId = raw.audit?.id ?? raw.audit_id ?? "";
  return {
    job: {
      id: jobId,
      created_at: raw.job?.created_at ?? createdAt,
      tenant_id: raw.job?.tenant_id ?? tenantId,
      transaction_id: raw.job?.transaction_id ?? raw.transaction_id ?? transactionId,
    },
    audit: {
      id: auditId,
      job_id: raw.audit?.job_id ?? jobId,
      events: raw.audit?.events ?? [],
    },
    findings: raw.findings ?? [],
    evidences: raw.evidences ?? [],
    transaction_id: raw.transaction_id ?? transactionId,
  };
}

export async function validateXml(payload: ValidateXmlRequest): Promise<ValidationResultV11> {
  const tenantId = getTenantId();
  const transactionId = payload.transaction_id ?? createTransactionId();
  const form = new FormData();
  form.append("xml_content", payload.xml);
  form.append("document_type", payload.document_type);
  if (payload.source) form.append("source", payload.source);

  const res = await fetch(`${API_BASE}/api/v1/validate/xml`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${getToken()}`,
      "X-Tenant-Id": tenantId,
      "X-Transaction-Id": transactionId,
    },
    body: form,
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "Erro de API");
    throw new Error(`API ${res.status}: ${detail}`);
  }
  const raw = (await res.json()) as ValidationResultApi;
  return adaptValidationResult(raw, tenantId, transactionId);
}

export async function getJobs(): Promise<Job[]> {
  const tenantId = getTenantId();
  const payload = await apiFetch<ApiJob[] | { items?: ApiJob[] }>("/api/v1/jobs");
  const rows = Array.isArray(payload) ? payload : payload.items ?? [];
  return rows.map((row) => normalizeJob(row, tenantId));
}

export async function getJob(jobId: string): Promise<Job | null> {
  const tenantId = getTenantId();
  const payload = await apiFetch<ApiJob>(`/api/v1/jobs/${jobId}`);
  return normalizeJob(payload, tenantId);
}

export async function getAudits(jobId?: string): Promise<AuditLog[]> {
  const tenantId = getTenantId();
  const q = jobId ? `?job_id=${encodeURIComponent(jobId)}` : "";
  const payload = await apiFetch<ApiAudit[] | { items?: ApiAudit[] }>(`/api/v1/audit${q}`);
  const rows = Array.isArray(payload) ? payload : payload.items ?? [];
  return rows.map((row) => normalizeAudit(row, tenantId));
}

export async function getAudit(jobId?: string): Promise<AuditLog[]> {
  return getAudits(jobId);
}

function contentDispositionFilename(raw: string | null): string | null {
  if (!raw) return null;
  const utf8 = raw.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8?.[1]) return decodeURIComponent(utf8[1]);
  const plain = raw.match(/filename="?([^";]+)"?/i);
  if (plain?.[1]) return plain[1];
  return null;
}

export async function exportJobEvidenceZip(jobId: string): Promise<JobEvidenceZipResult> {
  if (!jobId) {
    throw new Error("jobId obrigatório para exportar evidências.");
  }

  const res = await fetch(`${API_BASE}/api/v1/jobs/${encodeURIComponent(jobId)}/evidence.zip`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${getToken()}`,
      "X-Tenant-Id": getTenantId(),
      Accept: "application/zip",
    },
    cache: "no-store",
  });

  if (!res.ok) {
    if (res.status === 404 || res.status === 501) {
      throw new Error("Export via API ainda nao disponivel.");
    }
    const detail = await res.text().catch(() => "Erro de API");
    throw new Error(`API ${res.status}: ${detail}`);
  }

  const bytes = new Uint8Array(await res.arrayBuffer());
  const filename = contentDispositionFilename(res.headers.get("content-disposition")) ?? makeJobEvidenceZipFilename(jobId);
  return { filename, bytes };
}

export async function openExceptionRequest(payload: {
  job_id: string;
  finding_id: string;
  rule_id: string;
  justification: string;
  created_by: string;
}): Promise<ExceptionRequest> {
  const tenantId = getTenantId();
  const row = await apiFetch<ApiExceptionRequest>("/api/v1/exceptions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return normalizeException(row, tenantId);
}

export async function listExceptionRequests(): Promise<ExceptionRequest[]> {
  const tenantId = getTenantId();
  const payload = await apiFetch<ApiExceptionRequest[] | { items?: ApiExceptionRequest[] }>("/api/v1/exceptions");
  const rows = Array.isArray(payload) ? payload : payload.items ?? [];
  return rows.map((row) => normalizeException(row, tenantId));
}

export async function decideExceptionRequest(exceptionId: string, decision: ExceptionDecision): Promise<ExceptionRequest> {
  const tenantId = getTenantId();
  const row = await apiFetch<ApiExceptionRequest>(`/api/v1/exceptions/${encodeURIComponent(exceptionId)}/decision`, {
    method: "POST",
    body: JSON.stringify(decision),
  });
  return normalizeException(row, tenantId);
}

export type ReportListItem = {
  id: string;
  report_type: "validation" | "batch";
  job_id: string | null;
  report_hash: string;
  file_size: number | null;
  status: "generating" | "ready" | "error";
  created_at: string;
};

export async function listReports(params?: { report_type?: string; job_id?: string; limit?: number }): Promise<ReportListItem[]> {
  const q = new URLSearchParams();
  if (params?.report_type) q.set("report_type", params.report_type);
  if (params?.job_id) q.set("job_id", params.job_id);
  if (params?.limit) q.set("limit", String(params.limit));
  const qs = q.toString();
  try {
    const payload = await apiFetch<ReportListItem[]>(`/api/v1/reports${qs ? `?${qs}` : ""}`);
    return Array.isArray(payload) ? payload : [];
  } catch {
    return [];
  }
}

export async function getReportDownloadUrl(reportId: string): Promise<{ download_url: string; expires_at: string }> {
  return apiFetch(`/api/v1/reports/${encodeURIComponent(reportId)}/download`);
}

// ── XML Correction (MVP) ───────────────────────────────────────────────────

export async function generateCorrectedXml(payload: { document_type?: string; xml: string }): Promise<{
  document_id: string;
  storage_key: string;
  download_url: string;
  applied_corrections: string[];
  unresolved_findings: unknown[];
  created_at: string;
}> {
  const form = new FormData();
  form.append("xml_content", payload.xml);
  if (payload.document_type) form.append("document_type", payload.document_type);

  const token = getToken();
  const tenantId = getTenantId();
  const res = await fetch(`${API_BASE}/api/v1/validate/xml/correct`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Tenant-Id": tenantId,
    },
    body: form,
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "Erro ao gerar XML corrigido");
    throw new Error(`Correção ${res.status}: ${detail}`);
  }
  return (await res.json()) as any;
}

// ── Documents API ───────────────────────────────────────────────────────────
export type DocumentResponse = {
  id: string;
  doc_type: string;
  original_filename: string | null;
  storage_key: string;
  file_size: number | null;
  content_type: string | null;
  status: string;
  uploaded_at: string | null;
  created_at: string;
  fiscal_metadata: Record<string, unknown>;
};

export async function listDocuments(params?: {
  doc_type?: string;
  status?: string;
  limit?: number;
}): Promise<DocumentResponse[]> {
  const q = new URLSearchParams();
  if (params?.doc_type) q.set("doc_type", params.doc_type);
  if (params?.status) q.set("status", params.status);
  if (params?.limit) q.set("limit", String(params.limit));
  const qs = q.toString();
  try {
    const payload = await apiFetch<DocumentResponse[]>(`/api/v1/documents${qs ? `?${qs}` : ""}`);
    return Array.isArray(payload) ? payload : [];
  } catch {
    return [];
  }
}

export async function getDocumentDownloadUrl(
  documentId: string,
): Promise<{ download_url: string; expires_at: string }> {
  return apiFetch(`/api/v1/documents/${encodeURIComponent(documentId)}/download`);
}
