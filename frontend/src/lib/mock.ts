import {
  AuditLog,
  ChatApiResponse,
  ChatMessage,
  ChatRequest,
  Conversation,
  ExceptionDecision,
  ExceptionRequest,
  Job,
  JobStatus,
  ValidateXmlRequest,
  ValidationResultV11,
} from "./types";
import { validateXmlWithRules } from "./validation/xmlRules";

type MockJob = Job & {
  readyAt?: number;
  pendingValidation?: ValidationResultV11;
};

type MockState = {
  counter: number;
  conversations: Conversation[];
  jobs: MockJob[];
  audits: AuditLog[];
  exceptions: ExceptionRequest[];
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
      evidence: [{ type: "job", job_id: id, href: `/jobs/${id}`, label: "Job de validação" }],
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
    exceptions: [],
  };
}

function upsertConversation(state: MockState, conversation: Conversation): void {
  const idx = state.conversations.findIndex((c) => c.id === conversation.id);
  if (idx === -1) state.conversations.unshift(conversation);
  else state.conversations[idx] = conversation;
}

function addAudit(state: MockState, row: AuditLog): void {
  state.audits.unshift(row);
}

function syncTransitions(state: MockState): MockState {
  const now = Date.now();
  let changed = false;

  const jobs = state.jobs.map((job) => {
    if (job.status === "RUNNING" && job.readyAt && job.readyAt <= now) {
      changed = true;
      const succeededOutput = job.pendingValidation
        ? {
            status: "PASS",
            contract_version: "findings-evidence-v1.1",
            findings: job.pendingValidation.findings,
            evidences: job.pendingValidation.evidences,
          }
        : { status: "PASS", calculated_cbs: "0.00", calculated_ibs: "0.00" };

      return {
        ...job,
        status: "SUCCESS" as const,
        updatedAt: nowIso(),
        readyAt: undefined,
        pendingValidation: undefined,
        output: succeededOutput,
        reportMarkdown: job.pendingValidation
          ? "## Resultado\n\nValidação XML concluída com evidências auditáveis."
          : "## Relatório\n\nProcessamento concluído com sucesso.",
        findings: job.pendingValidation?.findings ?? job.findings,
        evidence: [
          ...(job.pendingValidation?.evidences.map((ev) => ({
            id: ev.id,
            type: ev.type,
            label: ev.label,
            href: ev.href,
            xpath: ev.xpath,
            snippet: ev.snippet,
          })) ?? job.evidence),
          {
            type: "audit" as const,
            audit_id: `audit-${job.id}`,
            href: `/audit?job_id=${job.id}`,
            label: "Audit log",
          },
          {
            type: "job" as const,
            job_id: job.id,
            href: `/jobs/${job.id}`,
            label: "Job",
          },
        ],
      };
    }
    return job;
  });

  if (!changed) {
    return state;
  }

  const existingAuditIds = new Set(state.audits.map((a) => a.id));
  const newAudits: AuditLog[] = [];
  for (const job of jobs) {
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
    jobs,
    audits: [...newAudits, ...state.audits],
  };
}

function makeMessage(role: "user" | "assistant", markdown: string): ChatMessage {
  return {
    id: `msg-${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    markdown,
    createdAt: nowIso(),
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

  const conversation =
    state.conversations.find((c) => c.id === payload.conversation_id) ??
    {
      id: `conv-${tenantId}-${String(state.counter++).padStart(4, "0")}`,
      title: message.slice(0, 42) || "Nova conversa",
      updatedAt: nowIso(),
      messages: [] as ChatMessage[],
    };

  conversation.messages.push(makeMessage("user", message));

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

    const assistant = makeMessage("assistant", assistantMarkdown);
    assistant.evidence = job.evidence;
    conversation.messages.push(assistant);
    conversation.updatedAt = nowIso();

    addAudit(state, {
      id: `audit-${jobId}-created`,
      tenantId,
      jobId,
      action: "chat_validation_started",
      createdAt: nowIso(),
      payload: { source: "chat", message },
    });

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
  conversation.messages.push(makeMessage("assistant", reply));
  conversation.updatedAt = nowIso();

  upsertConversation(state, conversation);
  saveState(tenantId, state);

  return {
    conversation_id: conversation.id,
    assistant_markdown: reply,
    evidence: [],
  };
}

export async function mockValidateXml(tenantId: string, payload: ValidateXmlRequest): Promise<ValidationResultV11> {
  const state = loadState(tenantId);
  const validation = validateXmlWithRules({
    tenantId,
    documentType: payload.document_type,
    xml: payload.xml,
  });

  const current = state.jobs.find((j) => j.id === validation.job.id);
  const findings = validation.findings;
  const evidence = validation.evidences.map((ev) => ({
    id: ev.id,
    type: ev.type,
    label: ev.label,
    href: ev.href,
    xpath: ev.xpath,
    snippet: ev.snippet,
  }));

  const job: MockJob = {
    id: validation.job.id,
    tenantId,
    jobType: "xml_validation",
    status: "RUNNING",
    createdAt: current?.createdAt ?? validation.job.created_at,
    updatedAt: nowIso(),
    input: {
      document_type: payload.document_type,
      source: payload.source ?? "paste",
    },
    output: null,
    reportMarkdown: "## Resultado\n\nValidação em processamento.",
    evidence,
    findings,
    readyAt: Date.now() + 1500,
    pendingValidation: validation,
  };

  if (current) {
    const idx = state.jobs.findIndex((j) => j.id === job.id);
    state.jobs[idx] = job;
  } else {
    state.jobs.unshift(job);
  }

  addAudit(state, {
    id: `${validation.audit.id}-started`,
    tenantId,
    jobId: validation.job.id,
    action: "xml_validation_started",
    createdAt: nowIso(),
    payload: {
      document_type: payload.document_type,
      findings_total: validation.findings.length,
    },
  });

  saveState(tenantId, state);
  return validation;
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

export async function mockOpenException(
  tenantId: string,
  payload: {
    job_id: string;
    finding_id: string;
    rule_id: string;
    justification: string;
    created_by: string;
  },
): Promise<ExceptionRequest> {
  const state = loadState(tenantId);
  const item: ExceptionRequest = {
    id: `exc-${tenantId}-${String(state.counter++).padStart(5, "0")}`,
    tenant_id: tenantId,
    job_id: payload.job_id,
    finding_id: payload.finding_id,
    rule_id: payload.rule_id,
    justification: payload.justification,
    status: "OPEN",
    created_by: payload.created_by,
    created_at: nowIso(),
  };
  state.exceptions.unshift(item);
  addAudit(state, {
    id: `audit-${item.id}-opened`,
    tenantId,
    jobId: payload.job_id,
    action: "exception_opened",
    createdAt: nowIso(),
    payload: {
      exception_id: item.id,
      finding_id: item.finding_id,
      rule_id: item.rule_id,
      retention: "5y-contractual",
    },
  });
  saveState(tenantId, state);
  return item;
}

export async function mockListExceptions(tenantId: string): Promise<ExceptionRequest[]> {
  const state = loadState(tenantId);
  return [...state.exceptions].sort((a, b) => b.created_at.localeCompare(a.created_at));
}

export async function mockDecideException(
  tenantId: string,
  exceptionId: string,
  decision: ExceptionDecision,
): Promise<ExceptionRequest> {
  const state = loadState(tenantId);
  const idx = state.exceptions.findIndex((row) => row.id === exceptionId);
  if (idx === -1) {
    throw new Error(`Exceção ${exceptionId} não encontrada.`);
  }
  const current = state.exceptions[idx];
  const next: ExceptionRequest = {
    ...current,
    status: decision.status,
    decided_by: decision.decided_by,
    decided_at: nowIso(),
    decision_comment: decision.decision_comment,
  };
  state.exceptions[idx] = next;

  addAudit(state, {
    id: `audit-${exceptionId}-${decision.status.toLowerCase()}`,
    tenantId,
    jobId: current.job_id,
    action: decision.status === "APPROVED" ? "exception_approved" : "exception_rejected",
    createdAt: nowIso(),
    payload: {
      exception_id: exceptionId,
      decision_comment: decision.decision_comment ?? "",
      decided_by: decision.decided_by,
      retention: "5y-contractual",
    },
  });

  saveState(tenantId, state);
  return next;
}


