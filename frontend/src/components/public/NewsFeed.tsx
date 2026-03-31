"use client";

import { useEffect, useState } from "react";

type NewsItem = {
  id: string;
  title: string;
  description: string;
  category: "Feature" | "Fix" | "Security";
  created_at: string;
};

type NewsFeedProps = {
  limit?: number;
  compact?: boolean;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

const MOCK_NEWS: NewsItem[] = [
  {
    id: "mock-1",
    title: "Motor CBS/IBS com 18 regras determinísticas",
    description:
      "Validação completa de notas fiscais contra as regras da LC 214 com evidências auditáveis por finding.",
    category: "Feature",
    created_at: "2026-03-28T00:00:00Z",
  },
  {
    id: "mock-2",
    title: "Calculadora CBS/IBS local para regime geral",
    description:
      "Calcule CBS e IBS por NCM, UF e CST sem autenticação. Gera snippet XML pronto para ERP.",
    category: "Feature",
    created_at: "2026-03-22T00:00:00Z",
  },
  {
    id: "mock-3",
    title: "Diagnóstico gratuito de XML fiscal",
    description:
      "Envie sua NF-e e receba um relatório completo de conformidade com a reforma tributária 2026.",
    category: "Feature",
    created_at: "2026-03-15T00:00:00Z",
  },
];

const categoryStyles: Record<NewsItem["category"], string> = {
  Feature: "bg-emerald-100 text-emerald-800",
  Fix: "bg-amber-100 text-amber-800",
  Security: "bg-rose-100 text-rose-800",
};

export function NewsFeed({ limit, compact = false }: NewsFeedProps) {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadNews() {
      const apiUrl = API_BASE || "(não configurado — usando fallback)";
      console.log("API URL em uso:", apiUrl);

      if (!API_BASE) {
        console.warn(
          "[NewsFeed] NEXT_PUBLIC_API_BASE_URL não está definido. " +
            "Configure a variável de ambiente no painel da Vercel. " +
            "Carregando mock de resiliência.",
        );
        if (active) {
          setItems(limit ? MOCK_NEWS.slice(0, limit) : MOCK_NEWS);
          setLoading(false);
        }
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/api/v1/news`, {
          cache: "no-store",
        });

        if (!res.ok) {
          throw new Error(`News endpoint retornou HTTP ${res.status} (${res.statusText})`);
        }

        const data = (await res.json()) as NewsItem[];
        if (!active) return;

        setItems(limit ? data.slice(0, limit) : data);
        setError("");
      } catch (err) {
        if (!active) return;
        const message = err instanceof Error ? err.message : String(err);
        console.error("[NewsFeed] Falha ao buscar notícias:", message, {
          url: `${API_BASE}/api/v1/news`,
          hint: message.includes("fetch") ? "Connection Refused / CORS" : "HTTP error",
        });
        // Resiliência: exibe mock enquanto a API não está disponível
        setItems(limit ? MOCK_NEWS.slice(0, limit) : MOCK_NEWS);
        setError("");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadNews();
    return () => {
      active = false;
    };
  }, [limit]);

  if (loading) {
    return (
      <div className={compact ? "grid gap-4 md:grid-cols-3" : "space-y-4"}>
        {Array.from({ length: limit ?? 3 }).map((_, index) => (
          <div
            key={index}
            className="animate-pulse rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
          >
            <div className="h-4 w-20 rounded-full bg-slate-200" />
            <div className="mt-4 h-6 w-3/4 rounded bg-slate-200" />
            <div className="mt-3 h-4 w-full rounded bg-slate-100" />
            <div className="mt-2 h-4 w-5/6 rounded bg-slate-100" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-3xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-900">
        {error}
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
        Nenhuma atualização publicada ainda.
      </div>
    );
  }

  return (
    <div className={compact ? "grid gap-4 md:grid-cols-3" : "space-y-4"}>
      {items.map((item) => (
        <article
          key={item.id}
          className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/60"
        >
          <div className="flex items-center justify-between gap-3">
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${categoryStyles[item.category]}`}
            >
              {item.category}
            </span>
            <time className="text-xs text-slate-500">
              {new Intl.DateTimeFormat("pt-BR", {
                day: "2-digit",
                month: "short",
                year: "numeric",
              }).format(new Date(item.created_at))}
            </time>
          </div>
          <h3 className="mt-4 text-lg font-semibold text-slate-900">{item.title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">{item.description}</p>
        </article>
      ))}
    </div>
  );
}
