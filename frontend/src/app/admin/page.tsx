"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import { getToken } from "@/lib/storage";
import { getPlanSlug } from "@/lib/plan";

// ── Types ───────────────────────────────────────────────────────────

type DayStat = { day: string; count: number };
type PlanDist = { plan: string; count: number };
type RevByPlan = { plan: string; count: number; total_cents: number };

type AdminStats = {
  generated_at: string;
  users: {
    total: number;
    active: number;
    trial: number;
    paid: number;
    cancelled: number;
    tenants: number;
    registrations_today: number;
    registrations_30d: DayStat[];
    plan_distribution: PlanDist[];
  };
  revenue: {
    mrr_cents: number;
    total_revenue_cents: number;
    revenue_month_cents: number;
    paid_count_month: number;
    pending_count: number;
    overdue_count: number;
    by_plan: RevByPlan[];
  };
  infra: {
    api_status: string;
    db_status: string;
    redis: {
      status: string;
      used_memory_human: string;
      connected_clients: number;
      uptime_days: number;
    };
  };
  site_traffic: {
    date: string;
    uniques: number;
    page_views: number;
    requests: number;
  } | null;
  validations: {
    today: number;
    month: number;
    total: number;
    last_7_days: DayStat[];
  };
  support: {
    open: number;
    in_progress: number;
    resolved: number;
    closed: number;
  };
  feedback: Record<string, number>;
};

// ── Helpers ─────────────────────────────────────────────────────────

function fmtBRL(cents: number): string {
  return `R$ ${(cents / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`}
    />
  );
}

// ── Reusable cards ──────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "green" | "red" | "blue" | "amber";
}) {
  const accentBorder = accent
    ? { green: "border-l-emerald-500", red: "border-l-red-500", blue: "border-l-blue-500", amber: "border-l-amber-500" }[accent]
    : "";
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${accent ? `border-l-4 ${accentBorder}` : ""}`}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

function MiniBar({ data, label }: { data: DayStat[]; label: string }) {
  if (data.length === 0) return null;
  const max = Math.max(...data.map((d) => d.count), 1);
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <div className="flex items-end gap-1" style={{ height: 80 }}>
        {data.map((d) => (
          <div key={d.day} className="group relative flex-1">
            <div
              className="w-full rounded-t bg-tribultz-500 transition-all hover:bg-tribultz-600"
              style={{ height: `${Math.max((d.count / max) * 100, 4)}%` }}
            />
            <div className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-slate-800 px-2 py-1 text-[10px] text-white opacity-0 shadow group-hover:opacity-100">
              {d.day.slice(5)}: {d.count}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-400">
        <span>{data[0]?.day.slice(5)}</span>
        <span>{data[data.length - 1]?.day.slice(5)}</span>
      </div>
    </div>
  );
}

function PlanDistributionTable({ data }: { data: PlanDist[] }) {
  const total = data.reduce((s, d) => s + d.count, 0) || 1;
  const colors: Record<string, string> = {
    trial: "bg-slate-400",
    starter: "bg-blue-400",
    profissional: "bg-tribultz-500",
    empresarial: "bg-purple-500",
    contador: "bg-amber-500",
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-500">
        Distribuicao por plano
      </p>
      {/* Bar */}
      <div className="mb-3 flex h-4 overflow-hidden rounded-full bg-slate-100">
        {data.map((d) => (
          <div
            key={d.plan}
            className={`${colors[d.plan] ?? "bg-slate-300"}`}
            style={{ width: `${(d.count / total) * 100}%` }}
            title={`${d.plan}: ${d.count}`}
          />
        ))}
      </div>
      {/* Legend */}
      <div className="flex flex-wrap gap-3 text-xs text-slate-600">
        {data.map((d) => (
          <span key={d.plan} className="flex items-center gap-1">
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${colors[d.plan] ?? "bg-slate-300"}`} />
            {d.plan} ({d.count})
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────

export default function AdminPage() {
  const router = useRouter();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const loadStats = useCallback(async () => {
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
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar dashboard admin.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    const plan = getPlanSlug();
    if (plan !== "admin") {
      router.replace("/dashboard");
      return;
    }
    loadStats();

    // Auto-refresh every 60s
    const interval = setInterval(loadStats, 60_000);
    return () => clearInterval(interval);
  }, [router, loadStats]);

  if (loading) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-tribultz-600" />
          <p className="text-sm text-slate-500">Carregando painel administrativo...</p>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-red-600">{error}</p>
          <button
            type="button"
            onClick={() => {
              setError(null);
              setLoading(true);
              loadStats();
            }}
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
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Painel Administrativo</h1>
          <p className="text-sm text-slate-500">
            Dados em tempo real do ecossistema Tribultz
            {lastRefresh && (
              <span className="ml-2 text-xs text-slate-400">
                (atualizado {lastRefresh.toLocaleTimeString("pt-BR")})
              </span>
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setLoading(true);
            loadStats();
          }}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
        >
          Atualizar
        </button>
      </div>

      {/* ── Usuarios ─────────────────────────── */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Usuarios
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total" value={s.users.total} accent="blue" />
          <StatCard label="Ativos" value={s.users.active} accent="green" />
          <StatCard label="Trial" value={s.users.trial} accent="amber" />
          <StatCard label="Pagantes" value={s.users.paid} accent="green" />
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatCard label="Cancelados" value={s.users.cancelled} accent="red" />
          <StatCard label="Tenants" value={s.users.tenants} />
          <StatCard label="Cadastros hoje" value={s.users.registrations_today} />
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <MiniBar data={s.users.registrations_30d} label="Cadastros (ultimos 30 dias)" />
          <PlanDistributionTable data={s.users.plan_distribution} />
        </div>
      </section>

      {/* ── Trafego do Site ──────────────────── */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Trafego do Site (hoje)
        </h2>
        {s.site_traffic ? (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard label="Visitantes unicos (aprox.)" value={s.site_traffic.uniques} accent="blue" />
              <StatCard label="Page views" value={s.site_traffic.page_views} />
              <StatCard label="Requisicoes totais" value={s.site_traffic.requests} />
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Fonte: Cloudflare Zone Analytics. &quot;Visitantes unicos&quot; e uma aproximacao
              de borda sobre todo o trafego HTTP da zona — inclui bots/crawlers, nao so
              humanos (o plano Free nao filtra por bot-score).
            </p>
          </>
        ) : (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-500">
            Cloudflare Analytics nao configurado (
            <code className="text-xs">CLOUDFLARE_ANALYTICS_TOKEN</code>).
          </div>
        )}
      </section>

      {/* ── Financeiro ────────────────────────── */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Financeiro
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="MRR"
            value={fmtBRL(s.revenue.mrr_cents)}
            sub="Receita mensal recorrente"
            accent="green"
          />
          <StatCard
            label="Receita total"
            value={fmtBRL(s.revenue.total_revenue_cents)}
            sub="Todos os pagamentos confirmados"
          />
          <StatCard
            label="Receita do mes"
            value={fmtBRL(s.revenue.revenue_month_cents)}
            sub={`${s.revenue.paid_count_month} pagamento(s)`}
            accent="blue"
          />
          <StatCard
            label="Pendentes / Atrasados"
            value={`${s.revenue.pending_count} / ${s.revenue.overdue_count}`}
            accent={s.revenue.overdue_count > 0 ? "red" : undefined}
          />
        </div>
        {s.revenue.by_plan.length > 0 && (
          <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-500">
              Receita por plano (mes atual)
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-slate-500">
                    <th className="pb-2">Plano</th>
                    <th className="pb-2 text-right">Pagamentos</th>
                    <th className="pb-2 text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {s.revenue.by_plan.map((r) => (
                    <tr key={r.plan} className="border-b last:border-0">
                      <td className="py-2 font-medium capitalize text-slate-800">{r.plan}</td>
                      <td className="py-2 text-right text-slate-600">{r.count}</td>
                      <td className="py-2 text-right font-semibold text-slate-900">
                        {fmtBRL(r.total_cents)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* ── Infraestrutura ────────────────────── */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Infraestrutura
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">API</p>
            <p className="mt-1 flex items-center gap-2 text-lg font-bold text-slate-900">
              <StatusDot ok={s.infra.api_status === "healthy"} />
              {s.infra.api_status === "healthy" ? "Online" : "Offline"}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Banco de dados</p>
            <p className="mt-1 flex items-center gap-2 text-lg font-bold text-slate-900">
              <StatusDot ok={s.infra.db_status === "healthy"} />
              {s.infra.db_status === "healthy" ? "Online" : "Offline"}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Redis</p>
            <p className="mt-1 flex items-center gap-2 text-lg font-bold text-slate-900">
              <StatusDot ok={s.infra.redis.status === "healthy"} />
              {s.infra.redis.status === "healthy" ? "Online" : "Offline"}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Memoria: {s.infra.redis.used_memory_human} · {s.infra.redis.connected_clients} conexoes · {s.infra.redis.uptime_days}d uptime
            </p>
          </div>
        </div>
      </section>

      {/* ── Validacoes ────────────────────────── */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Validacoes
        </h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard label="Hoje" value={s.validations.today} accent="blue" />
          <StatCard label="Este mes" value={s.validations.month} />
          <StatCard label="Total" value={s.validations.total} />
        </div>
        <div className="mt-4">
          <MiniBar data={s.validations.last_7_days} label="Validacoes (ultimos 7 dias)" />
        </div>
      </section>

      {/* ── Suporte & Feedback ────────────────── */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Suporte & Feedback
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <StatCard label="Tickets abertos" value={s.support.open} accent={s.support.open > 0 ? "red" : "green"} />
          <StatCard label="Em andamento" value={s.support.in_progress} accent="amber" />
          <StatCard label="Resolvidos" value={s.support.resolved} accent="green" />
          <StatCard label="Fechados" value={s.support.closed} />
          <StatCard
            label="Feedback (mes)"
            value={s.feedback.total ?? 0}
            sub={Object.entries(s.feedback)
              .filter(([k]) => k !== "total")
              .map(([k, v]) => `${k}: ${v}`)
              .join(" · ") || "Nenhum"}
          />
        </div>
      </section>
    </div>
  );
}
