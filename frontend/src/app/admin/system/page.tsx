"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type Health = {
  status: string;
  db: string;
  redis: string;
  asaas_api: string;
  ai_engine: string;
  hubspot: string;
  email: string;
  latency_ms: number;
};

const LABELS: Record<string, string> = {
  db: "PostgreSQL",
  redis: "Redis",
  asaas_api: "Asaas (pagamentos)",
  ai_engine: "AI engine (OpenRouter)",
  hubspot: "HubSpot (CRM)",
  email: "E-mail (Resend/SMTP)",
};

export default function AdminSystemPage() {
  const [data, setData] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetch(`${API_BASE}/health/ready`)
      .then((r) => r.json())
      .then((d) => alive && setData(d))
      .catch(() => alive && setError("Não foi possível obter a saúde do sistema."));
    return () => {
      alive = false;
    };
  }, []);

  const ok = (s: string | undefined) => s === "ok";

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-900">Saúde do sistema</h1>
      <p className="mb-5 text-sm text-slate-500">Probe profundo (/health/ready) das dependências de produção.</p>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {!data && !error && <p className="text-sm text-slate-500">Carregando…</p>}

      {data && (
        <>
          <div className={`mb-4 inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold ${ok(data.status) ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
            <span className={`h-2 w-2 rounded-full ${ok(data.status) ? "bg-green-500" : "bg-red-500"}`} />
            {ok(data.status) ? "Operacional" : "Degradado"} · {data.latency_ms} ms
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(LABELS).map(([key, label]) => {
              const status = (data as unknown as Record<string, string>)[key];
              return (
                <div key={key} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3">
                  <span className="text-sm font-medium text-slate-700">{label}</span>
                  <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${ok(status) ? "text-green-600" : "text-red-600"}`}>
                    <span className={`h-2 w-2 rounded-full ${ok(status) ? "bg-green-500" : "bg-red-500"}`} />
                    {ok(status) ? "ok" : status ?? "?"}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
