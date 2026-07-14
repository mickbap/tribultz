"use client";

import { useEffect, useState } from "react";

type NewsItem = {
  id: string;
  title: string;
  description: string;
  category: "Feature" | "Fix" | "Security" | "Advisory";
  created_at: string;
};

type NewsFeedProps = {
  limit?: number;
  compact?: boolean;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

const categoryStyles: Record<NewsItem["category"], string> = {
  Feature: "bg-emerald-100 text-emerald-800",
  Fix: "bg-amber-100 text-amber-800",
  Security: "bg-rose-100 text-rose-800",
  Advisory: "bg-blue-100 text-blue-800",
};

export function NewsFeed({ limit, compact = false }: NewsFeedProps) {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<string>("");

  useEffect(() => {
    let active = true;
    let intervalId: number | undefined;

    async function loadNews() {
      const base = API_BASE ? `${API_BASE}/api/v1/news` : "/api/v1/news";
      const newsUrl = limit ? `${base}?limit=${limit}` : base;

      if (!API_BASE) {
        console.warn(
          "[NewsFeed] NEXT_PUBLIC_API_BASE_URL não está definido. " +
            "Tentando carregar news por rota relativa /api/v1/news. " +
            "Se o frontend e a API estiverem em domínios diferentes, configure a variável de ambiente.",
        );
      }

      try {
        const res = await fetch(newsUrl, {
          cache: "no-store",
        });

        if (!res.ok) {
          throw new Error(`News endpoint retornou HTTP ${res.status} (${res.statusText})`);
        }

        const data = (await res.json()) as NewsItem[];
        if (!active) return;

        setItems(data);
        setLastUpdated(new Date().toLocaleTimeString("pt-BR", {
          hour: "2-digit",
          minute: "2-digit",
        }));
        setError("");
      } catch (err) {
        if (!active) return;
        const message = err instanceof Error ? err.message : String(err);
        console.warn("[NewsFeed] Falha ao buscar notícias:", message, {
          url: `${API_BASE}/api/v1/news`,
          hint: message.includes("fetch") ? "Connection Refused / CORS" : "HTTP error",
        });
        setItems([]);
        setError("Não foi possível carregar as atualizações no momento.");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadNews();
    intervalId = window.setInterval(loadNews, 60_000);

    return () => {
      active = false;
      if (intervalId) {
        window.clearInterval(intervalId);
      }
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
    <>
      {lastUpdated ? (
        <div className="mb-4 text-right text-xs text-slate-500">
          Atualizado automaticamente às {lastUpdated}
        </div>
      ) : null}
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
    </>
  );
}
