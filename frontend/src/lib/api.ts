import {
  ApiAudit,
  ApiExceptionRequest,
  ApiJob,
  AuditLog,
  ChatApiResponse,
  ChatRequest,
  Conversation,
  ExceptionDecision,
  ExceptionRequest,
  Job,
  NormalizedChatResponse,
  ValidateXmlRequest,
  ValidationResultV11,
  normalizeAudit,
  normalizeChatResponse,
  normalizeException,
  normalizeJob,
} from "./types";
import { buildJobEvidenceBundle } from "./export/jobEvidenceBundle";
import { buildJobEvidenceZip, makeJobEvidenceZipFilename } from "./export/jobEvidenceZip";
import {
  mockDecideException,
  mockGetConversation,
  mockGetJob,
  mockListAudits,
  mockListConversations,
  mockListExceptions,
  mockListJobs,
  mockOpenException,
  mockPostChatMessage,
  mockValidateXml,
  resetMockData,
} from "./mock";
import { getMockMode, getTenantId, getToken } from "./storage";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type LoginRequest = {
  email: string;
  password: string;
  tenant_slug: string;
};

type LoginResponse = {
  access_token: string;
  token_type?: string;
};

export type JobEvidenceZipResult = {
  filename: string;
  bytes: Uint8Array;
};

function headers(extra?: HeadersInit): HeadersInit {
  const token = getToken();
  const tenant = getTenantId();
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    "X-Tenant-Id": tenant,
    ...(extra ?? {}),
  };
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: headers(init.headers),
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
    const detail = await res.text().catch(() => "Erro ao autenticar");
    throw new Error(`Login ${res.status}: ${detail}`);
  }
  return (await res.json()) as LoginResponse;
}

export async function postChatMessage(payload: ChatRequest): Promise<NormalizedChatResponse> {
  const tenantId = getTenantId();
  if (getMockMode()) {
    const raw = await mockPostChatMessage(tenantId, payload);
    return normalizeChatResponse(raw);
  }
  const raw = await apiFetch<ChatApiResponse>("/api/v1/chat/message", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return normalizeChatResponse(raw);
}

export async function validateXml(payload: ValidateXmlRequest): Promise<ValidationResultV11> {
  const tenantId = getTenantId();
  if (getMockMode()) {
    return mockValidateXml(tenantId, payload);
  }
  return apiFetch<ValidationResultV11>("/api/v1/validate/xml", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listConversations(): Promise<Conversation[]> {
  if (getMockMode()) {
    return mockListConversations(getTenantId());
  }
  return [];
}

export async function getConversation(conversationId: string): Promise<Conversation | null> {
  if (getMockMode()) {
    return mockGetConversation(getTenantId(), conversationId);
  }
  return null;
}

export async function getJobs(): Promise<Job[]> {
  const tenantId = getTenantId();
  if (getMockMode()) {
    return mockListJobs(tenantId);
  }
  const payload = await apiFetch<ApiJob[] | { items?: ApiJob[] }>("/api/v1/jobs");
  const rows = Array.isArray(payload) ? payload : payload.items ?? [];
  return rows.map((row) => normalizeJob(row, tenantId));
}

export async function getJob(jobId: string): Promise<Job | null> {
  const tenantId = getTenantId();
  if (getMockMode()) {
    return mockGetJob(tenantId, jobId);
  }
  const payload = await apiFetch<ApiJob>(`/api/v1/jobs/${jobId}`);
  return normalizeJob(payload, tenantId);
}

export async function getAudits(jobId?: string): Promise<AuditLog[]> {
  const tenantId = getTenantId();
  if (getMockMode()) {
    return mockListAudits(tenantId, jobId);
  }
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
    throw new Error("jobId obrigatorio para exportar evidencias.");
  }

  if (getMockMode()) {
    const job = await getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} nao encontrado.`);
    }
    const audits = await getAudits(jobId);
    const bundle = buildJobEvidenceBundle(job, audits);
    const bytes = buildJobEvidenceZip(bundle);
    return {
      filename: makeJobEvidenceZipFilename(job.id),
      bytes,
    };
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
  if (getMockMode()) {
    return mockOpenException(tenantId, payload);
  }
  const row = await apiFetch<ApiExceptionRequest>("/api/v1/exceptions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return normalizeException(row, tenantId);
}

export async function listExceptionRequests(): Promise<ExceptionRequest[]> {
  const tenantId = getTenantId();
  if (getMockMode()) {
    return mockListExceptions(tenantId);
  }
  const payload = await apiFetch<ApiExceptionRequest[] | { items?: ApiExceptionRequest[] }>("/api/v1/exceptions");
  const rows = Array.isArray(payload) ? payload : payload.items ?? [];
  return rows.map((row) => normalizeException(row, tenantId));
}

export async function decideExceptionRequest(exceptionId: string, decision: ExceptionDecision): Promise<ExceptionRequest> {
  const tenantId = getTenantId();
  if (getMockMode()) {
    return mockDecideException(tenantId, exceptionId, decision);
  }
  const row = await apiFetch<ApiExceptionRequest>(`/api/v1/exceptions/${encodeURIComponent(exceptionId)}/decision`, {
    method: "POST",
    body: JSON.stringify(decision),
  });
  return normalizeException(row, tenantId);
}

export function resetDemoData(): void {
  resetMockData(getTenantId());
}
