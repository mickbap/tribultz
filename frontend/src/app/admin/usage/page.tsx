"use client";

import { useAdminData } from "@/lib/useAdminData";

type Usage = {
  generated_at: string;
  jobs: { today: number; month: number; total: number };
  api_keys: { total: number; active: number; credits_balance: number; used_today: number };
};

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
    </div>
  );
}

export default function AdminUsagePage() {
  const { data, error, loading } = useAdminData<Usage>("/api/v1/admin/usage");

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-900">Uso &amp; Operações</h1>
      <p className="mb-5 text-sm text-slate-500">Validações (jobs) e consumo da API pública.</p>

      {loading && <p className="text-sm text-slate-500">Carregando…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <div className="space-y-6">
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Validações (jobs)</h2>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              <Stat label="Hoje" value={data.jobs.today} />
              <Stat label="Mês" value={data.jobs.month} />
              <Stat label="Total" value={data.jobs.total} />
            </div>
          </section>
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">API pública (pay-per-call)</h2>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Stat label="API Keys" value={data.api_keys.total} />
              <Stat label="Ativas" value={data.api_keys.active} />
              <Stat label="Créditos (ativos)" value={data.api_keys.credits_balance} />
              <Stat label="Usadas hoje" value={data.api_keys.used_today} />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
