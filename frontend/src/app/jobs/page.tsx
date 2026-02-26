"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Skeleton } from "@/components/common/Skeleton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Toast } from "@/components/common/Toast";
import { getJobs } from "@/lib/api";
import { exportEvidenceZipAndDownload } from "@/lib/export/evidenceExportUi";
import { Job, JobStatus } from "@/lib/types";

type PeriodFilter = "24h" | "7d" | "30d" | "all";

function withinPeriod(dateIso: string, period: PeriodFilter): boolean {
  if (period === "all") return true;
  const age = Date.now() - new Date(dateIso).getTime();
  if (period === "24h") return age <= 24 * 60 * 60 * 1000;
  if (period === "7d") return age <= 7 * 24 * 60 * 60 * 1000;
  return age <= 30 * 24 * 60 * 60 * 1000;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ tone: "success" | "error" | "info"; message: string } | null>(null);
  const [exportingByJobId, setExportingByJobId] = useState<Record<string, boolean>>({});

  const [status, setStatus] = useState<JobStatus | "ALL">("ALL");
  const [period, setPeriod] = useState<PeriodFilter>("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    setLoading(true);
    getJobs()
      .then(setJobs)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs.filter((job) => {
      if (status !== "ALL" && job.status !== status) return false;
      if (!withinPeriod(job.createdAt, period)) return false;
      if (!q) return true;
      return [job.id, job.jobType, job.status].some((text) => text.toLowerCase().includes(q));
    });
  }, [jobs, status, period, query]);

  async function handleExport(jobId: string): Promise<void> {
    setExportingByJobId((prev) => ({ ...prev, [jobId]: true }));
    const feedback = await exportEvidenceZipAndDownload(jobId);
    setToast(feedback);
    setExportingByJobId((prev) => ({ ...prev, [jobId]: false }));
  }

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Jobs</h1>
        <p className="text-sm text-slate-500">Rastreabilidade de validações e reprocessamentos.</p>
      </header>

      <div className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-4">
        <label className="text-sm">
          <span className="mb-1 block text-slate-500">Status</span>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as JobStatus | "ALL")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
          >
            <option value="ALL">Todos</option>
            <option value="QUEUED">QUEUED</option>
            <option value="RUNNING">RUNNING</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="FAILED">FAILED</option>
          </select>
        </label>

        <label className="text-sm">
          <span className="mb-1 block text-slate-500">Período</span>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value as PeriodFilter)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
          >
            <option value="24h">24h</option>
            <option value="7d">7 dias</option>
            <option value="30d">30 dias</option>
            <option value="all">Todo período</option>
          </select>
        </label>

        <label className="text-sm md:col-span-2">
          <span className="mb-1 block text-slate-500">Busca</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="job id, tipo ou status"
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </label>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhum job encontrado para os filtros selecionados.</p>
        ) : (
          <div className="scroll-thin overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="px-2 py-2">ID</th>
                  <th className="px-2 py-2">Tipo</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2">Criado em</th>
                  <th className="px-2 py-2">Ação</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((job) => (
                  <tr key={job.id} className="border-b border-slate-100">
                    <td className="px-2 py-2 font-medium text-slate-800">{job.id}</td>
                    <td className="px-2 py-2 text-slate-600">{job.jobType}</td>
                    <td className="px-2 py-2">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-2 py-2 text-slate-500">{new Date(job.createdAt).toLocaleString()}</td>
                    <td className="px-2 py-2">
                      <div className="flex flex-wrap items-center gap-3">
                        <Link href={`/jobs/${job.id}`} className="text-tribultz-700 hover:underline">
                          Abrir detalhe
                        </Link>
                        <button
                          type="button"
                          disabled={!!exportingByJobId[job.id]}
                          onClick={() => void handleExport(job.id)}
                          className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {exportingByJobId[job.id] ? "Exportando…" : "Exportar evidências"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {error ? <Toast message={error} tone="error" onClose={() => setError(null)} /> : null}
      {toast ? <Toast message={toast.message} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}
