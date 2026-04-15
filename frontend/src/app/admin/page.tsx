"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import { getToken } from "@/lib/storage";
import { getPlanSlug } from "@/lib/plan";

type AdminStats = {
  users: { total: number; active: number; trial: number; paid: number };
  revenue: { mrr_cents: number; pending_count: number; paid_count: number };
  infra: { api_status: string; worker_status: string; redis_status: string };
  validations: { today: number; month: number };
};

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const plan = getPlanSlug();
    if (plan !== "admin") {
      router.replace("/dashboard");
      return;
    }

    async function loadStats() {
      const token = getToken();
      if (!token) {
        router.replace("/login");
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/api/v1/admin/dashboard`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (res.status === 403) {
          router.replace("/dashboard");
          return;
        }

        if (!res.ok) throw new Error(`Erro ${res.status}`);
        setStats(await res.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erro ao carregar dashboard admin.");
      } finally {
        setLoading(false);
      }
    }

    loadStats();
  }, [router]);

  if (loading) {
    return (
      <main className="grid min-h-screen place-items-center">
        <p className="text-sm text-slate-500">Carregando painel administrativo...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="grid min-h-screen place-items-center">
        <div className="text-center">
          <p className="text-sm text-red-600">{error}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-3 text-sm text-tribultz-600 underline"
          >
            Tentar novamente
          </button>
        </div>
      </main>
    );
  }

  const s = stats!;

  return (
    <main className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Painel Administrativo</h1>
            <p className="text-sm text-slate-500">Dados em tempo real do ecossistema Tribultz</p>
          </div>
          <button
            type="button"
            onClick={() => {
              localStorage.clear();
              window.dispatchEvent(new Event("tribultz-settings-updated"));
              router.push("/login");
            }}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
          >
            Sair
          </button>
        </div>

        {/* Usuarios */}
        <section className="mb-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Usuarios</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total" value={s.users.total} />
            <StatCard label="Ativos" value={s.users.active} />
            <StatCard label="Trial" value={s.users.trial} />
            <StatCard label="Pagantes" value={s.users.paid} />
          </div>
        </section>

        {/* Financeiro */}
        <section className="mb-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Financeiro</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard
              label="MRR"
              value={`R$ ${(s.revenue.mrr_cents / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`}
              sub="Receita mensal recorrente"
            />
            <StatCard label="Pagos (mes)" value={s.revenue.paid_count} />
            <StatCard label="Pendentes" value={s.revenue.pending_count} />
          </div>
        </section>

        {/* Infra */}
        <section className="mb-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Infraestrutura</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="API" value={s.infra.api_status} />
            <StatCard label="Worker" value={s.infra.worker_status} />
            <StatCard label="Redis" value={s.infra.redis_status} />
          </div>
        </section>

        {/* Validacoes */}
        <section className="mb-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Validacoes</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <StatCard label="Hoje" value={s.validations.today} />
            <StatCard label="Este mes" value={s.validations.month} />
          </div>
        </section>
      </div>
    </main>
  );
}
