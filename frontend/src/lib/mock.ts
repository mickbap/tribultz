import { AuditLog, ChatApiResponse, ChatMessage, ChatRequest, Conversation, Evidence, Job, JobStatus } from "./types";

type MockJob = Job & { readyAt?: number };

type MockState = {
  counter: number;
  conversations: Conversation[];
  jobs: MockJob[];
  audits: AuditLog[];
};

const TENANT_COUNT = 20;

function nowIso(): string {
  return new Date().toISOString();
}

function seedFromTenant(tenantId: string): number {
  let h = 2166136261;
  for (let i = 0; i < tenantId.length; i += 1) {
    h ^= tenantId.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

function lcg(seed: number): () => number {
  let x = seed || 123456;
  return () => {
    x = (x * 1103515245 + 12345) % 2147483648;
    return x / 2147483648;
  };
}

function stateKey(tenantId: string): string {
  return `tribultz.mock.state.${tenantId}`;
}

function loadState(tenantId: string): MockState {
  if (typeof window === "undefined") return bootstrapState(tenantId);
  const raw = localStorage.getItem(stateKey(tenantId));
  if (!raw) {
    const state = bootstrapState(tenantId);
    saveState(tenantId, state);
    return state;
  }
  const parsed = JSON.parse(raw) as MockState;
  const synced = syncTransitions(parsed);
  saveState(tenantId, synced);
  return synced;
}

function saveState(tenantId: string, state: MockState): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(stateKey(tenantId), JSON.stringify(state));
}

function bootstrapState(tenantId: string): MockState {
  const rand = lcg(seedFromTenant(tenantId));
  const jobs: MockJob[] = [];
  const audits: AuditLog[] = [];

  for (let i = 0; i < TENANT_COUNT; i += 1) {
    const id = `job-${tenantId}-${String(i + 1).padStart(4, "0")}`;
    const statuses: JobStatus[] = ["SUCCESS", "FAILED", "RUNNING", "QUEUED"];
    const status = statuses[Math.floor(rand() * statuses.length)];
    const createdAt = new Date(Date.now() - (i + 1) * 3_600_000).toISOString();
    const evidence: Evidence[] = [{ type: "job", job_id: id, href: `/jobs/${id}`, label: "Job de validação" }];

    jobs.push({
      id,
      tenantId,
      jobType: "task_a_validate_cbs_ibs",
      status,
      createdAt,
      updatedAt: createdAt,
      input: {
        invoice_number: `INV-${1000 + i}`,
        declared_cbs: "0",
        declared_ibs: "0",
      },
      output:
        status === "SUCCESS"
          ? {
              status: "PASS",
              calculated_cbs: "0.00",
              calculated_ibs: "0.00",
            }
          : status === "FAILED"
            ? { error: "Validation mismatch" }
            : null,
      reportMarkdown:
        status === "SUCCESS"
          ? `## Relatório\n\nValidação concluída para **INV-${1000 + i}** com status **PASS**.`
          : null,
      evidence,
      readyAt: status === "RUNNING" ? Date.now() + 90_000 + i * 250 : undefined,
    });

    audits.push({
      id: `audit-${tenantId}-${String(i + 1).padStart(4, "0")}`,
      tenantId,
      jobId: id,
      action: status === "FAILED" ? "validation_failed" : "validation_processed",
      createdAt,
      payload: {
        status,
        checksum: `CHK-${tenantId}-${i + 1}`,
      },
    });
  }

  const conversationId = `conv-${tenantId}-0001`;
  const conversations: Conversation[] = [
    {
      id: conversationId,
      title: "Boas-vindas",
      updatedAt: nowIso(),
      messages: [
        {
          id: `msg-${tenantId}-welcome`,
          role: "assistant",
          markdown: "Olá. Use o botão **Validar CBS/IBS** para iniciar uma validação com evidências rastreáveis.",
          createdAt: nowIso(),
        },
      ],
    },
  ];

  return {
    counter: TENANT_COUNT + 1,
    conversations,
    jobs,
    audits,
  };
}

function syncTransitions(state: MockState): MockState {
  const changed = state.jobs.some((job) => job.status === "RUNNING" && job.readyAt && job.readyAt <= Date.now());
  if (!changed) return state;

  const updatedJobs = state.jobs.map((job) => {
    if (job.status === "RUNNING" && job.readyAt && job.readyAt <= Date.now()) {
      return {
        ...job,
        status: "SUCCESS" as const,
        updatedAt: nowIso(),
        readyAt: undefined,
        output: { status: "PASS", calculated_cbs: "0.00", calculated_ibs: "0.00" },
        reportMarkdown: "## Relatório\n\nProcessamento concluído com sucesso.",
        evidence: [
          ...job.evidence,
          {
            type: "audit" as const,
            audit_id: `audit-${job.id}`,
            href: `/audit?job_id=${job.id}`,
            label: "Audit log",
          },
        ],
      };
    }
    return job;
  });

  const existingAuditIds = new Set(state.audits.map((a) => a.id));
  const newAudits: AuditLog[] = [];
  for (const job of updatedJobs) {
    if (job.status === "SUCCESS") {
      const auditId = `audit-${job.id}`;
      if (!existingAuditIds.has(auditId)) {
        newAudits.push({
          id: auditId,
          tenantId: job.tenantId,
          jobId: job.id,
          action: "validation_succeeded",
          createdAt: nowIso(),
          payload: { status: "SUCCESS", source: "mock-transition" },
        });
      }
    }
  }

  return {
    ...state,
    jobs: updatedJobs,
    audits: [...newAudits, ...state.audits],
  };
}

export function resetMockData(tenantId: string): void {
  saveState(tenantId, bootstrapState(tenantId));
}

export async function mockListConversations(tenantId: string): Promise<Conversation[]> {
  const state = loadState(tenantId);
  return [...state.conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export async function mockGetConversation(tenantId: string, conversationId: string): Promise<Conversation | null> {
  const state = loadState(tenantId);
  return state.conversations.find((c) => c.id === conversationId) ?? null;
}

export async function mockPostChatMessage(tenantId: string, payload: ChatRequest): Promise<ChatApiResponse> {
  const state = loadState(tenantId);
  const message = payload.message.trim();
  const isValidate = /validate|validar|cbs|ibs/i.test(message);

  let conversation =
    state.conversations.find((c) => c.id === payload.conversation_id) ??
    {
      id: `conv-${tenantId}-${String(state.counter++).padStart(4, "0")}`,
      title: message.slice(0, 42) || "Nova conversa",
      updatedAt: nowIso(),
      messages: [] as ChatMessage[],
    };

  const userMsg: ChatMessage = {
    id: `msg-${tenantId}-${String(state.counter++).padStart(5, "0")}`,
    role: "user",
    markdown: message,
    createdAt: nowIso(),
  };
  conversation.messages.push(userMsg);

  if (isValidate) {
    const jobId = `job-${tenantId}-live-${String(state.counter++).padStart(4, "0")}`;
    const jobHref = `/jobs/${jobId}`;

    const job: MockJob = {
      id: jobId,
      tenantId,
      jobType: "task_a_validate_cbs_ibs",
      status: "RUNNING",
      createdAt: nowIso(),
      updatedAt: nowIso(),
      input: { message },
      output: null,
      reportMarkdown: null,
      evidence: [{ type: "job", job_id: jobId, href: jobHref, label: "Job de validação" }],
      readyAt: Date.now() + 3500,
    };
    state.jobs.unshift(job);

    const assistantMarkdown = [
      "## Resultado",
      "- **Status:** OK",
      "- **Resumo executivo:** Validação iniciada com sucesso.",
      "",
      "## Evidências",
      `- **Job:** [Job de validação](${jobHref}) — \`job_id=${jobId}\``,
      "",
      "## Observações / Premissas",
      "- **Premissas consideradas:** dados da mensagem.",
      "- **Limites / Incertezas:** sujeito a regras do tenant.",
      "- **Recomendação prática:** acompanhe o job até SUCCESS.",
    ].join("\n");

    const assistant: ChatMessage = {
      id: `msg-${tenantId}-${String(state.counter++).padStart(5, "0")}`,
      role: "assistant",
      markdown: assistantMarkdown,
      evidence: job.evidence,
      createdAt: nowIso(),
    };
    conversation.messages.push(assistant);
    conversation.updatedAt = nowIso();

    upsertConversation(state, conversation);
    saveState(tenantId, state);

    return {
      conversation_id: conversation.id,
      response_markdown: assistantMarkdown,
      job_id: jobId,
      job_href: jobHref,
      evidence: job.evidence,
    };
  }

  const reply = "Posso ajudar com validações fiscais. Clique em **Validar CBS/IBS** para iniciar.";
  const assistant: ChatMessage = {
    id: `msg-${tenantId}-${String(state.counter++).padStart(5, "0")}`,
    role: "assistant",
    markdown: reply,
    createdAt: nowIso(),
  };
  conversation.messages.push(assistant);
  conversation.updatedAt = nowIso();

  upsertConversation(state, conversation);
  saveState(tenantId, state);

  return {
    conversation_id: conversation.id,
    assistant_markdown: reply,
    evidence: [],
  };
}

function upsertConversation(state: MockState, conversation: Conversation): void {
  const idx = state.conversations.findIndex((c) => c.id === conversation.id);
  if (idx === -1) state.conversations.unshift(conversation);
  else state.conversations[idx] = conversation;
}

export async function mockListJobs(tenantId: string): Promise<Job[]> {
  const state = loadState(tenantId);
  return [...state.jobs].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export async function mockGetJob(tenantId: string, jobId: string): Promise<Job | null> {
  const state = loadState(tenantId);
  return state.jobs.find((job) => job.id === jobId) ?? null;
}

export async function mockListAudits(tenantId: string, jobId?: string): Promise<AuditLog[]> {
  const state = loadState(tenantId);
  const filtered = jobId ? state.audits.filter((log) => log.jobId === jobId) : state.audits;
  return [...filtered].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

