"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Skeleton } from "@/components/common/Skeleton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Toast } from "@/components/common/Toast";
import { getAudits, getJobs } from "@/lib/api";
import { AuditLog, Job } from "@/lib/types";

function percent(success: number, total: number): string {
  if (!total) return "0%";
  return `${Math.round((success / total) * 100)}%`;
}

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [audits, setAudits] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([getJobs(), getAudits()])
      .then(([jobsData, auditsData]) => {
        setJobs(jobsData);
        setAudits(auditsData);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const metrics = useMemo(() => {
    const jobs24h = jobs.filter((job) => Date.now() - new Date(job.createdAt).getTime() <= 24 * 60 * 60 * 1000);
    const successCount = jobs.filter((job) => job.status === "SUCCESS").length;
    const failedCount = jobs.filter((job) => job.status === "FAILED").length;
    return {
      total24h: jobs24h.length,
      successRate: percent(successCount, jobs.length),
      exceptionsOpen: failedCount,
    };
  }, [jobs]);

  return (
    <section className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Painel</h1>
        <p className="text-sm text-slate-500">Visão executiva da operação tributária.</p>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Jobs 24h</p>
          <p className="mt-2 text-3xl font-bold">{loading ? "..." : metrics.total24h}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Validações aprovadas %</p>
          <p className="mt-2 text-3xl font-bold">{loading ? "..." : metrics.successRate}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Exceções abertas</p>
          <p className="mt-2 text-3xl font-bold">{loading ? "..." : metrics.exceptionsOpen}</p>
        </article>
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
