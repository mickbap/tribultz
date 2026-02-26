"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { JsonViewer } from "@/components/common/JsonViewer";
import { Skeleton } from "@/components/common/Skeleton";
import { Toast } from "@/components/common/Toast";
import { getAudits } from "@/lib/api";
import { exportEvidenceZipAndDownload } from "@/lib/export/evidenceExportUi";
import { AuditLog } from "@/lib/types";

function AuditContent() {
  const searchParams = useSearchParams();
  const jobIdFromUrl = searchParams.get("job_id") ?? "";
  const auditIdFromUrl = searchParams.get("audit_id") ?? "";

  const [audits, setAudits] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ tone: "success" | "error" | "info"; message: string } | null>(null);
  const [query, setQuery] = useState(jobIdFromUrl);
  const [actionFilter, setActionFilter] = useState("");
  const [selected, setSelected] = useState<AuditLog | null>(null);
  const [exportingByJobId, setExportingByJobId] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setLoading(true);
    setQuery(jobIdFromUrl || auditIdFromUrl);
    const load = auditIdFromUrl ? getAudits() : getAudits(jobIdFromUrl || undefined);
    load
      .then((rows) => {
        if (auditIdFromUrl) {
          setAudits(rows.filter((row) => row.id === auditIdFromUrl));
          return;
        }
        setAudits(rows);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [jobIdFromUrl, auditIdFromUrl]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const action = actionFilter.trim().toLowerCase();
    return audits.filter((row) => {
      if (q) {
        const haystack = [row.id, row.jobId ?? "", row.action].join(" ").toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      if (action && !row.action.toLowerCase().includes(action)) return false;
      return true;
    });
  }, [audits, query, actionFilter]);

  async function handleExport(jobId: string): Promise<void> {
    setExportingByJobId((prev) => ({ ...prev, [jobId]: true }));
    const feedback = await exportEvidenceZipAndDownload(jobId);
    setToast(feedback);
    setExportingByJobId((prev) => ({ ...prev, [jobId]: false }));
  }

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Auditoria</h1>
        <p className="text-sm text-slate-500">Rastreamento de eventos por job, tenant e ação.</p>
      </header>

      <div className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-2">
        <label className="text-sm">
          <span className="mb-1 block text-slate-500">Filtro por Job ID</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="job_id, action, audit id"
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-500">Filtro por ação</span>
          <input
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            placeholder="validation_succeeded"
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
          <p className="text-sm text-slate-500">Nenhum evento de auditoria encontrado.</p>
        ) : (
          <div className="scroll-thin overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="px-2 py-2">Quando</th>
                  <th className="px-2 py-2">Ação</th>
                  <th className="px-2 py-2">Job</th>
                  <th className="px-2 py-2">Detalhe</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id} className="border-b border-slate-100">
                    <td className="px-2 py-2 text-slate-600">{new Date(item.createdAt).toLocaleString()}</td>
                    <td className="px-2 py-2 font-medium text-slate-800">{item.action}</td>
                    <td className="px-2 py-2 text-slate-600">{item.jobId ?? "-"}</td>
                    <td className="px-2 py-2">
                      <div className="flex flex-wrap items-center gap-3">
                        <button
                          type="button"
                          onClick={() => setSelected(item)}
                          className="text-tribultz-700 hover:underline"
                        >
                          Ver JSON
                        </button>
                        {item.jobId ? (
                          <button
                            type="button"
                            disabled={!!exportingByJobId[item.jobId]}
                            onClick={() => void handleExport(item.jobId as string)}
                            className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {exportingByJobId[item.jobId] ? "Exportando…" : "Exportar evidências"}
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selected ? (
        <div className="fixed inset-0 z-40 bg-slate-900/40" role="dialog" aria-modal="true">
          <div className="mx-auto mt-10 w-[95%] max-w-2xl rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-800">Detalhe da auditoria</p>
                <p className="text-xs text-slate-500">{selected.id}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="rounded border border-slate-300 px-2 py-1 text-xs"
              >
                Fechar
              </button>
            </div>
            <JsonViewer title="Payload" data={selected.payload} />
          </div>
        </div>
      ) : null}

      {error ? <Toast message={error} tone="error" onClose={() => setError(null)} /> : null}
      {toast ? <Toast message={toast.message} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}

export default function AuditPage() {
  return (
    <Suspense fallback={<Skeleton className="h-24 w-full" />}>
      <AuditContent />
    </Suspense>
  );
}
