import {
  ApiAudit,
  ApiJob,
  AuditLog,
  ChatApiResponse,
  ChatRequest,
  Conversation,
  Job,
  NormalizedChatResponse,
  normalizeAudit,
  normalizeChatResponse,
  normalizeJob,
} from "./types";
import {
  mockGetConversation,
  mockGetJob,
  mockListAudits,
  mockListConversations,
  mockListJobs,
  mockPostChatMessage,
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
  const rows = Array.isArray(payload) ? payload : (payload.items ?? []);
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
  const rows = Array.isArray(payload) ? payload : (payload.items ?? []);
  return rows.map((row) => normalizeAudit(row, tenantId));
}

export async function getAudit(jobId?: string): Promise<AuditLog[]> {
  return getAudits(jobId);
}

export function resetDemoData(): void {
  resetMockData(getTenantId());
}
