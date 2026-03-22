"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Skeleton } from "@/components/common/Skeleton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Toast } from "@/components/common/Toast";
import { getAudits, getJobs, listExceptionRequests } from "@/lib/api";
import { AuditLog, ExceptionRequest, Finding, Job } from "@/lib/types";
import { getAccountType, getTenantId, getTenants, type StoredTenant } from "@/lib/storage";

function percent(success: number, total: number): string {
  if (!total) return "0%";
  return `${Math.round((success / total) * 100)}%`;
}

type RuleViolation = { rule_id: string; count: number };

function topRules(jobs: Job[], limit: number): RuleViolation[] {
  const counts = new Map<string, number>();
  for (const job of jobs) {
    if (!job.findings) continue;
    for (const f of job.findings) {
      counts.set(f.rule_id, (counts.get(f.rule_id) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .map(([rule_id, count]) => ({ rule_id, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}

type TrendDay = { label: string; count: number; pass: number; fail: number };

function trendLast7Days(jobs: Job[]): TrendDay[] {
  const days: TrendDay[] = [];
  const now = new Date();

  for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    const label = `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
    const dayJobs = jobs.filter((j) => j.createdAt.slice(0, 10) === key);
    const pass = dayJobs.filter((j) => j.status === "SUCCESS").length;
    days.push({ label, count: dayJobs.length, pass, fail: dayJobs.length - pass });
  }

  return days;
}

function TrendChart({ data }: { data: TrendDay[] }) {
  const maxCount = Math.max(...data.map((d) => d.count), 1);

  return (
    <div className="flex items-end gap-2" style={{ height: 120 }}>
      {data.map((day) => {
        const totalH = Math.max((day.count / maxCount) * 100, 2);
        const passH = day.count > 0 ? (day.pass / day.count) * totalH : 0;
        const failH = totalH - passH;
        return (
          <div key={day.label} className="flex flex-1 flex-col items-center gap-1">
            <div className="flex w-full flex-col items-center" style={{ height: 100 }}>
              <div className="flex-1" />
              <div className="w-full max-w-8 flex flex-col">
                {failH > 0 && (
                  <div
                    className="w-full rounded-t bg-red-400"
                    style={{ height: `${failH}px` }}
                    title={`FAIL: ${day.fail}`}
                  />
                )}
                {passH > 0 && (
                  <div
                    className={`w-full bg-emerald-500 ${failH > 0 ? "" : "rounded-t"} rounded-b`}
                    style={{ height: `${passH}px` }}
                    title={`PASS: ${day.pass}`}
                  />
                )}
                {day.count === 0 && (
                  <div className="w-full rounded bg-slate-200" style={{ height: "2px" }} />
                )}
              </div>
            </div>
            <span className="text-[10px] text-slate-500">{day.label}</span>
            <span className="text-[10px] font-medium text-slate-700">{day.count}</span>
          </div>
        );
      })}
    </div>
  );
}

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [audits, setAudits] = useState<AuditLog[]>([]);
  const [exceptions, setExceptions] = useState<ExceptionRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantIdState] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [accountType, setAccType] = useState("empresa");
  const [tenantCount, setTenantCount] = useState(0);

  useEffect(() => {
    const tid = getTenantId();
    const tenants = getTenants();
    const accType = getAccountType();
    setTenantIdState(tid);
    setAccType(accType);
    setTenantCount(tenants.length);
    const match = tenants.find((t) => t.id === tid) ?? tenants.find((t) => t.slug === tid);
    setTenantName(match?.name ?? tid);

    setLoading(true);
    Promise.all([getJobs(), getAudits(), listExceptionRequests()])
      .then(([jobsData, auditsData, exceptionsData]) => {
        setJobs(jobsData);
        setAudits(auditsData);
        setExceptions(exceptionsData);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const metrics = useMemo(() => {
    const jobs24h = jobs.filter((job) => Date.now() - new Date(job.createdAt).getTime() <= 24 * 60 * 60 * 1000);
    const successCount = jobs.filter((job) => job.status === "SUCCESS").length;
    const openExceptions = exceptions.filter((row) => row.status === "OPEN").length;
    const totalFindings = jobs.reduce((sum, j) => sum + (j.findings?.length ?? 0), 0);
    const fatalFindings = jobs.reduce(
      (sum, j) => sum + (j.findings?.filter((f) => f.severity === "FATAL").length ?? 0),
      0,
    );
    return {
      total24h: jobs24h.length,
      totalJobs: jobs.length,
      successRate: percent(successCount, jobs.length),
      exceptionsOpen: openExceptions,
      totalFindings,
      fatalFindings,
    };
  }, [jobs, exceptions]);

  const top3Rules = useMemo(() => topRules(jobs, 3), [jobs]);
  const trend = useMemo(() => trendLast7Days(jobs), [jobs]);

  return (
    <section className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Painel</h1>
        <p className="text-sm text-slate-500">Visão executiva da operação tributária.</p>
      </header>

      <div className={`flex items-center gap-3 rounded-xl border p-4 ${
        accountType === "contador"
          ? "border-amber-200 bg-amber-50"
          : "border-slate-200 bg-white"
      }`}>
        <div className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold ${
          accountType === "contador"
            ? "bg-amber-100 text-amber-700"
            : "bg-tribultz-100 text-tribultz-700"
        }`}>
          {accountType === "contador" ? "CT" : "TB"}
        </div>
        <div className="flex-1">
          <p className="text-sm font-semibold text-slate-800">
            Tenant ativo: <span className="font-mono">{tenantName}</span>
          </p>
          <p className="text-xs text-slate-500">
            {accountType === "contador"
              ? `Conta Contador — ${tenantCount > 1 ? `${tenantCount} CNPJs vinculados` : "1 CNPJ vinculado"}. Dados abaixo referem-se ao CNPJ selecionado.`
              : "Conta Empresa — dados exclusivos do seu CNPJ."}
          </p>
        </div>
        {accountType === "contador" && (
          <Link
            href="/settings"
            className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-50"
          >
            Gerenciar CNPJs
          </Link>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Jobs 24h</p>
          <p className="mt-2 text-3xl font-bold">{loading ? "..." : metrics.total24h}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Total Validações</p>
          <p className="mt-2 text-3xl font-bold">{loading ? "..." : metrics.totalJobs}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Taxa Conformidade</p>
          <p className="mt-2 text-3xl font-bold text-emerald-600">{loading ? "..." : metrics.successRate}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Exceções Abertas</p>
          <p className="mt-2 text-3xl font-bold">{loading ? "..." : metrics.exceptionsOpen}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Total Findings</p>
          <p className="mt-2 text-3xl font-bold">{loading ? "..." : metrics.totalFindings}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">FATAL</p>
          <p className="mt-2 text-3xl font-bold text-red-600">{loading ? "..." : metrics.fatalFindings}</p>
        </article>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="rounded-xl border border-slate-200 bg-white p-4 lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Trend (7 dias)</h2>
          {loading ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <>
              <TrendChart data={trend} />
              <div className="mt-2 flex items-center gap-4 text-xs text-slate-500">
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" /> PASS
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-full bg-red-400" /> FAIL
                </span>
              </div>
            </>
          )}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Top 3 Regras Violadas</h2>
          {loading ? (
            <Skeleton className="h-20 w-full" />
          ) : top3Rules.length === 0 ? (
            <p className="text-sm text-slate-500">Sem violações registradas.</p>
          ) : (
            <ul className="space-y-2">
              {top3Rules.map((rule, idx) => (
                <li key={rule.rule_id} className="flex items-center justify-between rounded border border-slate-100 p-2">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-600">
                      {idx + 1}
                    </span>
                    <span className="font-mono text-sm">{rule.rule_id}</span>
                  </div>
                  <span className="text-sm font-semibold text-red-600">{rule.count}x</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Últimos 5 Jobs</h2>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : jobs.length === 0 ? (
            <p className="text-sm text-slate-500">Sem jobs recentes.</p>
          ) : (
            <ul className="space-y-2">
              {jobs.slice(0, 5).map((job) => (
                <li key={job.id} className="flex items-center justify-between rounded border border-slate-100 p-2">
                  <div>
                    <Link href={`/jobs/${job.id}`} className="text-sm font-medium text-tribultz-700 hover:underline">
                      {job.id}
                    </Link>
                    <p className="text-xs text-slate-500">{new Date(job.createdAt).toLocaleString()}</p>
                  </div>
                  <StatusBadge status={job.status} />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Últimos 5 logs de auditoria</h2>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : audits.length === 0 ? (
            <p className="text-sm text-slate-500">Sem eventos.</p>
          ) : (
            <ul className="space-y-2">
              {audits.slice(0, 5).map((audit) => (
                <li key={audit.id} className="rounded border border-slate-100 p-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-slate-800">{audit.action}</span>
                    <Link href={`/audit?job_id=${audit.jobId ?? ""}`} className="text-xs text-tribultz-700 hover:underline">
                      Ver na auditoria
                    </Link>
                  </div>
                  <p className="text-xs text-slate-500">{new Date(audit.createdAt).toLocaleString()}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {error ? <Toast message={error} tone="error" onClose={() => setError(null)} /> : null}
    </section>
  );
}
