"use client";

import { useEffect, useMemo, useState } from "react";
import { EvidenceList } from "@/components/chat/EvidenceList";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { Skeleton } from "@/components/common/Skeleton";
import { Toast } from "@/components/common/Toast";
import { getConversation, listConversations, postChatMessage } from "@/lib/api";
import { ChatMessage, Conversation } from "@/lib/types";

const VALIDATE_CTA = "Validar CBS/IBS do documento INV-999 e retornar evidências.";

function upsertConversation(list: Conversation[], item: Conversation): Conversation[] {
  const idx = list.findIndex((row) => row.id === item.id);
  const next = [...list];
  if (idx === -1) next.unshift(item);
  else next[idx] = item;
  return next.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

function makeMessage(role: "user" | "assistant", markdown: string, evidence?: ChatMessage["evidence"]): ChatMessage {
  return {
    id: `tmp-${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    markdown,
    createdAt: new Date().toISOString(),
    evidence,
  };
}

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load(): Promise<void> {
      setLoading(true);
      try {
        const rows = await listConversations();
        setConversations(rows);
        if (rows.length && !activeConversationId) {
          setActiveConversationId(rows[0].id);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Falha ao carregar conversas.");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  const activeConversation = useMemo(
    () => conversations.find((conv) => conv.id === activeConversationId) ?? null,
    [conversations, activeConversationId],
  );

  async function sendMessage(rawMessage?: string): Promise<void> {
    const message = (rawMessage ?? draft).trim();
    if (!message || sending) return;

    setSending(true);
    setError(null);
    setDrawerOpen(false);

    const localConversationId = activeConversationId;
    const userMessage = makeMessage("user", message);

    setConversations((prev) => {
      const target = prev.find((c) => c.id === localConversationId);
      const base: Conversation =
        target ?? {
          id: localConversationId ?? `local-${Date.now()}`,
          title: message.slice(0, 48) || "Nova conversa",
          updatedAt: new Date().toISOString(),
          messages: [],
        };
      return upsertConversation(prev, {
        ...base,
        messages: [...base.messages, userMessage],
        updatedAt: new Date().toISOString(),
      });
    });
    setDraft("");

    try {
      const response = await postChatMessage({
        conversation_id: localConversationId,
        message,
      });

      const assistant = makeMessage("assistant", response.assistantMarkdown, response.evidence);
      const serverConversation = await getConversation(response.conversationId);

      setConversations((prev) => {
        if (serverConversation) {
          return upsertConversation(prev, serverConversation);
        }

        const target = prev.find((c) => c.id === localConversationId || c.id === response.conversationId);
        const base: Conversation =
          target ?? {
            id: response.conversationId,
            title: message.slice(0, 48) || "Nova conversa",
            updatedAt: new Date().toISOString(),
            messages: [],
          };

        return upsertConversation(prev, {
          ...base,
          id: response.conversationId,
          messages: [...base.messages, assistant],
          updatedAt: new Date().toISOString(),
        });
      });

      setActiveConversationId(response.conversationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao enviar mensagem.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="grid gap-4 lg:grid-cols-[18rem_1fr]">
      <aside className="hidden rounded-2xl border border-slate-200 bg-white lg:block">
        <div className="border-b border-slate-200 px-4 py-3">
          <h1 className="text-sm font-semibold text-slate-700">Conversas</h1>
        </div>
        <div className="scroll-thin max-h-[70vh] overflow-auto p-2">
          {loading ? (
            <div className="space-y-2 p-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : conversations.length === 0 ? (
            <p className="p-2 text-sm text-slate-500">Nenhuma conversa ainda.</p>
          ) : (
            <ul className="space-y-1">
              {conversations.map((conversation) => {
                const active = conversation.id === activeConversationId;
                return (
                  <li key={conversation.id}>
                    <button
                      type="button"
                      onClick={() => setActiveConversationId(conversation.id)}
                      className={`w-full rounded-lg px-3 py-2 text-left ${
                        active ? "bg-tribultz-100 text-tribultz-700" : "hover:bg-slate-100"
                      }`}
                    >
                      <p className="truncate text-sm font-medium">{conversation.title}</p>
                      <p className="text-xs text-slate-500">{new Date(conversation.updatedAt).toLocaleString()}</p>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </aside>

      <section className="flex min-h-[70vh] flex-col rounded-2xl border border-slate-200 bg-white">
        <header className="flex items-center gap-2 border-b border-slate-200 px-4 py-3">
          <button
            type="button"
            className="rounded border border-slate-300 px-2 py-1 text-xs lg:hidden"
            onClick={() => setDrawerOpen(true)}
          >
            Conversas
          </button>
          <h2 className="text-sm font-semibold text-slate-700">Novo Chat</h2>
          <div className="ml-auto">
            <button
              type="button"
              onClick={() => void sendMessage(VALIDATE_CTA)}
              disabled={sending}
              className="rounded-lg bg-tribultz-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-tribultz-700 disabled:cursor-not-allowed disabled:opacity-70"
            >
              Validar CBS/IBS
            </button>
          </div>
        </header>

        <div className="scroll-thin flex-1 space-y-4 overflow-auto p-4">
          {loading ? (
            <div className="space-y-4">
              <Skeleton className="h-24 w-2/3" />
              <Skeleton className="ml-auto h-20 w-2/3" />
            </div>
          ) : !activeConversation || activeConversation.messages.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-500">
              Sem mensagens. Envie uma mensagem para iniciar.
            </div>
          ) : (
            activeConversation.messages.map((message) => (
              <article
                key={message.id}
                className={`max-w-3xl rounded-xl border p-3 ${
                  message.role === "user"
                    ? "ml-auto border-tribultz-200 bg-tribultz-50"
                    : "border-slate-200 bg-white"
                }`}
              >
                <p className="mb-2 text-[11px] uppercase tracking-wide text-slate-500">{message.role}</p>
                <MarkdownRenderer markdown={message.markdown} />
                {message.evidence?.length ? <EvidenceList evidence={message.evidence} /> : null}
              </article>
            ))
          )}
        </div>

        <div className="border-t border-slate-200 p-4">
          <label className="sr-only" htmlFor="chat-compose">
            Digite sua mensagem
          </label>
          <textarea
            id="chat-compose"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void sendMessage();
              }
            }}
            placeholder="Digite sua mensagem fiscal..."
            className="min-h-24 w-full resize-y rounded-xl border border-slate-300 p-3 text-sm"
          />
          <div className="mt-2 flex justify-end">
            <button
              type="button"
              onClick={() => void sendMessage()}
              disabled={sending || !draft.trim()}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {sending ? "Enviando..." : "Enviar"}
            </button>
          </div>
        </div>
      </section>

      {drawerOpen ? (
        <div className="fixed inset-0 z-40 bg-slate-900/40 lg:hidden" role="dialog" aria-modal="true">
          <div className="h-full w-72 bg-white">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <span className="font-semibold">Conversas</span>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                className="rounded border border-slate-300 px-2 py-1 text-xs"
              >
                Fechar
              </button>
            </div>
            <div className="scroll-thin max-h-[88vh] overflow-auto p-2">
              <ul className="space-y-1">
                {conversations.map((conversation) => {
                  const active = conversation.id === activeConversationId;
                  return (
                    <li key={conversation.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setActiveConversationId(conversation.id);
                          setDrawerOpen(false);
                        }}
                        className={`w-full rounded-lg px-3 py-2 text-left ${
                          active ? "bg-tribultz-100 text-tribultz-700" : "hover:bg-slate-100"
                        }`}
                      >
                        <p className="truncate text-sm font-medium">{conversation.title}</p>
                        <p className="text-xs text-slate-500">{new Date(conversation.updatedAt).toLocaleString()}</p>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </div>
      ) : null}

      {error ? <Toast message={error} tone="error" onClose={() => setError(null)} /> : null}
    </section>
  );
}


