"use client";

import { FormEvent, useEffect, useState } from "react";
import { Toast } from "@/components/common/Toast";
import { apiFetch } from "@/lib/api";
import { getMockMode } from "@/lib/storage";

type Tab = "ticket" | "feedback" | "errors";
type Priority = "low" | "medium" | "high" | "critical";
type TicketStatus = "open" | "in_progress" | "resolved" | "closed";

interface Ticket {
  id: string;
  title: string;
  description: string;
  status: TicketStatus;
  priority: Priority;
  created_at: string;
}

interface KnownError {
  id: string;
  code: string;
  title: string;
  description: string;
  severity: string;
  workaround: string | null;
  github_issue_url: string | null;
  resolved_at: string | null;
  created_at: string;
}

const PRIORITY_LABELS: Record<Priority, string> = {
  low: "Baixa",
  medium: "Média",
  high: "Alta",
  critical: "Crítica",
};

const STATUS_LABELS: Record<TicketStatus, string> = {
  open: "Aberto",
  in_progress: "Em andamento",
  resolved: "Resolvido",
  closed: "Encerrado",
};

const STATUS_COLORS: Record<TicketStatus, string> = {
  open: "bg-blue-100 text-blue-700",
  in_progress: "bg-yellow-100 text-yellow-700",
  resolved: "bg-green-100 text-green-700",
  closed: "bg-slate-100 text-slate-500",
};

const SEVERITY_COLORS: Record<string, string> = {
  low: "bg-slate-100 text-slate-600",
  medium: "bg-yellow-100 text-yellow-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

// ── Mock data ──────────────────────────────────────────────────────────────────

const MOCK_TICKETS: Ticket[] = [
  {
    id: "mock-1",
    title: "Erro ao validar NF-e com NCM 10063000",
    description: "A validação retorna erro inesperado.",
    status: "in_progress",
    priority: "high",
    created_at: new Date().toISOString(),
  },
];

const MOCK_ERRORS: KnownError[] = [
  {
    id: "mock-e1",
    code: "ERR-001",
    title: "Timeout em XMLs acima de 5MB",
    description: "Documentos XML maiores que 5MB podem causar timeout no parser.",
    severity: "medium",
    workaround: "Divida o arquivo em lotes menores antes de enviar.",
    github_issue_url: "https://github.com/mickbap/tribultz/issues/170",
    resolved_at: null,
    created_at: new Date().toISOString(),
  },
];

// ── Component ──────────────────────────────────────────────────────────────────

export default function SupportPage() {
  const [tab, setTab] = useState<Tab>("ticket");
  const [toast, setToast] = useState<{ tone: "success" | "error" | "info"; msg: string } | null>(null);

  // Ticket form
  const [ticketTitle, setTicketTitle] = useState("");
  const [ticketDesc, setTicketDesc] = useState("");
  const [ticketPriority, setTicketPriority] = useState<Priority>("medium");
  const [ticketLoading, setTicketLoading] = useState(false);

  // Feedback form
  const [fbCategory, setFbCategory] = useState<"bug" | "sugestao" | "elogio" | "feature">("sugestao");
  const [fbTitle, setFbTitle] = useState("");
  const [fbMessage, setFbMessage] = useState("");
  const [fbLoading, setFbLoading] = useState(false);

  // Data
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [errors, setErrors] = useState<KnownError[]>([]);
  const [loadingTickets, setLoadingTickets] = useState(false);
  const [loadingErrors, setLoadingErrors] = useState(false);

  useEffect(() => {
    if (getMockMode()) {
      setTickets(MOCK_TICKETS);
      setErrors(MOCK_ERRORS);
      return;
    }
    fetchTickets();
    fetchErrors();
  }, []);

  async function fetchTickets() {
    setLoadingTickets(true);
    try {
      const data = await apiFetch<Ticket[]>("/api/v1/support/tickets");
      setTickets(data);
    } catch {
      // silent — user might not have tickets yet
    } finally {
      setLoadingTickets(false);
    }
  }

  async function fetchErrors() {
    setLoadingErrors(true);
    try {
      const data = await apiFetch<KnownError[]>("/api/v1/support/errors");
      setErrors(data);
    } catch {
      // silent
    } finally {
      setLoadingErrors(false);
    }
  }

  async function submitTicket(e: FormEvent) {
    e.preventDefault();
    setToast(null);

    if (ticketTitle.trim().length < 5) {
      setToast({ tone: "error", msg: "Título deve ter no mínimo 5 caracteres." });
      return;
    }
    if (ticketDesc.trim().length < 20) {
      setToast({ tone: "error", msg: "Descrição deve ter no mínimo 20 caracteres." });
      return;
    }

    if (getMockMode()) {
      setToast({ tone: "success", msg: "Ticket registrado (modo demo). Nossa equipe entrará em contato." });
      setTicketTitle("");
      setTicketDesc("");
      return;
    }

    setTicketLoading(true);
    try {
      const ticket = await apiFetch<Ticket>("/api/v1/support/tickets", {
        method: "POST",
        body: JSON.stringify({ title: ticketTitle.trim(), description: ticketDesc.trim(), priority: ticketPriority }),
      });
      setTickets((prev) => [ticket, ...prev]);
      setToast({ tone: "success", msg: "Ticket aberto com sucesso. Você receberá um email de confirmação." });
      setTicketTitle("");
      setTicketDesc("");
    } catch (err) {
      setToast({ tone: "error", msg: err instanceof Error ? err.message : "Falha ao abrir ticket." });
    } finally {
      setTicketLoading(false);
    }
  }

  async function submitFeedback(e: FormEvent) {
    e.preventDefault();
    setToast(null);

    if (fbMessage.trim().length < 10) {
      setToast({ tone: "error", msg: "Mensagem deve ter no mínimo 10 caracteres." });
      return;
    }

    if (getMockMode()) {
      setToast({ tone: "success", msg: "Feedback registrado (modo demo). Obrigado!" });
      setFbTitle("");
      setFbMessage("");
      return;
    }

    setFbLoading(true);
    try {
      await apiFetch("/api/v1/support/feedback", {
        method: "POST",
        body: JSON.stringify({ category: fbCategory, title: fbTitle.trim() || fbCategory, message: fbMessage.trim() }),
      });
      setToast({ tone: "success", msg: "Feedback enviado! Você receberá um email de agradecimento." });
      setFbTitle("");
      setFbMessage("");
    } catch (err) {
      setToast({ tone: "error", msg: err instanceof Error ? err.message : "Falha ao enviar feedback." });
    } finally {
      setFbLoading(false);
    }
  }

  return (
    <section className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Suporte</h1>
        <p className="text-sm text-slate-500">
          Abra um ticket, envie feedback ou consulte erros conhecidos da plataforma.
        </p>
      </header>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1 w-fit">
        {(["ticket", "feedback", "errors"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === t ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t === "ticket" ? "Suporte" : t === "feedback" ? "Feedback" : "Erros Conhecidos"}
          </button>
        ))}
      </div>

      {/* ── Ticket Tab ── */}
      {tab === "ticket" && (
        <div className="grid gap-6 lg:grid-cols-2">
          <form onSubmit={submitTicket} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6">
            <h2 className="font-semibold text-slate-900">Abrir ticket de suporte</h2>

            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">Assunto</span>
              <input
                type="text"
                value={ticketTitle}
                onChange={(e) => setTicketTitle(e.target.value)}
                placeholder="Descreva o problema resumidamente"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                maxLength={200}
              />
            </label>

            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">Prioridade</span>
              <select
                value={ticketPriority}
                onChange={(e) => setTicketPriority(e.target.value as Priority)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                {(Object.keys(PRIORITY_LABELS) as Priority[]).map((k) => (
                  <option key={k} value={k}>{PRIORITY_LABELS[k]}</option>
                ))}
              </select>
            </label>

            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">Descrição detalhada</span>
              <textarea
                value={ticketDesc}
                onChange={(e) => setTicketDesc(e.target.value)}
                placeholder="Descreva o problema com o máximo de detalhes possível. Inclua passos para reproduzir, mensagens de erro, XMLs de exemplo..."
                className="min-h-36 w-full rounded-lg border border-slate-300 p-3 text-sm"
                maxLength={5000}
              />
              <span className="text-xs text-slate-400">{ticketDesc.length}/5000</span>
            </label>

            <button
              type="submit"
              disabled={ticketLoading}
              className="w-full rounded-lg bg-tribultz-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-tribultz-700 disabled:opacity-70"
            >
              {ticketLoading ? "Abrindo ticket..." : "Abrir ticket"}
            </button>

            <p className="text-xs text-slate-400">
              Após o envio, você receberá um email de confirmação em contato@tribultz.com.br.
            </p>
          </form>

          {/* Ticket list */}
          <div className="space-y-3">
            <h2 className="font-semibold text-slate-900">Seus tickets</h2>
            {loadingTickets && <p className="text-sm text-slate-500">Carregando...</p>}
            {!loadingTickets && tickets.length === 0 && (
              <p className="text-sm text-slate-400">Nenhum ticket aberto ainda.</p>
            )}
            {tickets.map((t) => (
              <div key={t.id} className="rounded-xl border border-slate-200 bg-white p-4 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium text-slate-900 leading-snug">{t.title}</p>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[t.status]}`}>
                    {STATUS_LABELS[t.status]}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-400">
                  <span>Prioridade: {PRIORITY_LABELS[t.priority]}</span>
                  <span>{new Date(t.created_at).toLocaleDateString("pt-BR")}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Feedback Tab ── */}
      {tab === "feedback" && (
        <form onSubmit={submitFeedback} className="max-w-lg space-y-4 rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="font-semibold text-slate-900">Enviar feedback</h2>

          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Categoria</span>
            <select
              value={fbCategory}
              onChange={(e) => setFbCategory(e.target.value as typeof fbCategory)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              <option value="bug">Bug / Problema</option>
              <option value="feature">Sugestão de funcionalidade</option>
              <option value="sugestao">Sugestão geral</option>
              <option value="elogio">Elogio</option>
            </select>
          </label>

          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Título</span>
            <input
              type="text"
              value={fbTitle}
              onChange={(e) => setFbTitle(e.target.value)}
              placeholder="Resumo do seu feedback"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              maxLength={200}
            />
          </label>

          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Mensagem</span>
            <textarea
              value={fbMessage}
              onChange={(e) => setFbMessage(e.target.value)}
              placeholder="Descreva sua sugestão, experiência ou problema..."
              className="min-h-32 w-full rounded-lg border border-slate-300 p-3 text-sm"
              maxLength={2000}
            />
            <span className="text-xs text-slate-400">{fbMessage.length}/2000</span>
          </label>

          <button
            type="submit"
            disabled={fbLoading}
            className="w-full rounded-lg bg-tribultz-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-tribultz-700 disabled:opacity-70"
          >
            {fbLoading ? "Enviando..." : "Enviar feedback"}
          </button>

          <p className="text-xs text-slate-400">
            Você receberá um email de agradecimento após o envio.
          </p>
        </form>
      )}

      {/* ── Known Errors Tab ── */}
      {tab === "errors" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Erros conhecidos</h2>
            <span className="text-xs text-slate-400">{errors.length} registrado{errors.length !== 1 ? "s" : ""}</span>
          </div>

          {loadingErrors && <p className="text-sm text-slate-500">Carregando...</p>}
          {!loadingErrors && errors.length === 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
              <p className="text-sm text-slate-500">Nenhum erro conhecido registrado.</p>
              <p className="text-xs text-slate-400 mt-1">Isso é uma boa notícia!</p>
            </div>
          )}

          {errors.map((err) => (
            <div
              key={err.id}
              className={`rounded-xl border bg-white p-5 space-y-3 ${err.resolved_at ? "border-green-200 opacity-70" : "border-slate-200"}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-400">{err.code}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_COLORS[err.severity] ?? "bg-slate-100 text-slate-600"}`}>
                      {err.severity.charAt(0).toUpperCase() + err.severity.slice(1)}
                    </span>
                    {err.resolved_at && (
                      <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                        Resolvido
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-semibold text-slate-900">{err.title}</p>
                </div>
                {err.github_issue_url && (
                  <a
                    href={err.github_issue_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 text-xs text-tribultz-600 hover:underline"
                  >
                    Ver no GitHub
                  </a>
                )}
              </div>

              <p className="text-sm text-slate-600 leading-relaxed">{err.description}</p>

              {err.workaround && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
                  <p className="text-xs font-semibold text-amber-700 mb-1">Contorno</p>
                  <p className="text-sm text-amber-800">{err.workaround}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {toast ? <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}
