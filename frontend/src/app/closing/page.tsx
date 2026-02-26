"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Skeleton } from "@/components/common/Skeleton";
import { Toast } from "@/components/common/Toast";
import { getAudits, getJobs, listExceptionRequests } from "@/lib/api";
import { createClosingSnapshot } from "@/lib/closing/aggregate";
import { AuditLog, ExceptionRequest, Job } from "@/lib/types";

export default function ClosingPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [audits, setAudits] = useState<AuditLog[]>([]);
  const [exceptions, setExceptions] = useState<ExceptionRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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

  const snapshot = useMemo(() => createClosingSnapshot({ jobs, audits, exceptions }), [jobs, audits, exceptions]);

  return (
    <section className="space-y-5">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold text-slate-900">Painel de Fechamento</h1>
        <p className="text-sm text-slate-500">Janela de 7 dias com consolidacao de jobs, auditoria e excecoes.</p>
        <p className="text-xs text-slate-400">
          Janela ativa: {new Date(snapshot.since).toLocaleString()} ate {new Date(snapshot.until).toLocaleString()}
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Fatals detectados (7d)</p>
          <p className="mt-2 text-3xl font-bold">{loading ? "..." : snapshot.counts.fatalFindings}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Excecoes abertas (7d)</p>
          <p className="mt-2 text-3xl font-bold">{loading ? "..." : snapshot.counts.openExceptions}</p>
          <Link href="/exceptions" className="mt-2 inline-block text-xs text-tribultz-700 hover:underline">
            Abrir fila de excecoes
          </Link>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Jobs executados (7d)</p>
          <p className="mt-2 text-3xl font-bold">{loading ? "..." : snapshot.counts.jobsExecuted}</p>
          <Link href="/jobs" className="mt-2 inline-block text-xs text-tribultz-700 hover:underline">
            Abrir lista de jobs
          </Link>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Audits recentes (7d)</p>
          <p className="mt-2 text-3xl font-bold">{loading ? "..." : snapshot.counts.recentAudits}</p>
          <Link href="/audit" className="mt-2 inline-block text-xs text-tribultz-700 hover:underline">
            Abrir auditoria
          </Link>
        </article>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Ultimos jobs (7d)</h2>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : snapshot.recentJobs.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum job na janela.</p>
          ) : (
            <ul className="space-y-2">
              {snapshot.recentJobs.map((row) => (
                <li key={row.id} className="rounded border border-slate-100 p-2">
                  <div className="flex items-center justify-between gap-3">
                    <Link href={`/jobs/${row.id}`} className="text-sm font-medium text-tribultz-700 hover:underline">
                      {row.id}
                    </Link>
                    <span className="text-xs text-slate-500">{row.status}</span>
                  </div>
                  <p className="text-xs text-slate-500">{new Date(row.createdAt).toLocaleString()}</p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Ultimos audits (7d)</h2>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : snapshot.recentAuditRows.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum audit na janela.</p>
          ) : (
            <ul className="space-y-2">
              {snapshot.recentAuditRows.map((row) => (
                <li key={row.id} className="rounded border border-slate-100 p-2">
                  <p className="text-sm font-medium text-slate-800">{row.action}</p>
                  <p className="text-xs text-slate-500">{new Date(row.createdAt).toLocaleString()}</p>
                  <div className="mt-1 flex flex-wrap gap-3">
                    <Link href={`/audit?audit_id=${encodeURIComponent(row.id)}`} className="text-xs text-tribultz-700 hover:underline">
                      Ver audit
                    </Link>
                    {row.jobId ? (
                      <Link href={`/jobs/${row.jobId}`} className="text-xs text-tribultz-700 hover:underline">
                        Abrir job
                      </Link>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Excecoes abertas (7d)</h2>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : snapshot.openExceptionRows.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhuma excecao aberta na janela.</p>
          ) : (
            <ul className="space-y-2">
              {snapshot.openExceptionRows.map((row) => (
                <li key={row.id} className="rounded border border-slate-100 p-2">
                  <p className="text-sm font-medium text-slate-800">{row.id}</p>
                  <p className="text-xs text-slate-500">
                    job_id: {row.job_id} | finding_id: {row.finding_id}
                  </p>
                  <div className="mt-1 flex flex-wrap gap-3">
                    <Link href="/exceptions" className="text-xs text-tribultz-700 hover:underline">
                      Ver excecoes
                    </Link>
                    <Link href={`/jobs/${row.job_id}`} className="text-xs text-tribultz-700 hover:underline">
                      Abrir job
                    </Link>
                  </div>
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
