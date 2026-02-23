"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { EvidenceList } from "@/components/chat/EvidenceList";
import { JsonViewer } from "@/components/common/JsonViewer";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { Skeleton } from "@/components/common/Skeleton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Toast } from "@/components/common/Toast";
import { getJob } from "@/lib/api";
import { Job } from "@/lib/types";

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params.id) return;
    setLoading(true);
    getJob(params.id)
      .then(setJob)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [params.id]);

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Detalhe do Job</h1>
          <p className="text-sm text-slate-500">Inspeção completa de entrada, saída e trilha de evidências.</p>
        </div>
        {job ? <StatusBadge status={job.status} /> : null}
      </header>

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : !job ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
          Job não encontrado.
        </div>
      ) : (
        <>
          <section className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-2">
            <div>
              <p className="text-xs uppercase text-slate-500">Job ID</p>
              <p className="mt-1 break-all font-semibold text-slate-800">{job.id}</p>
            </div>
            <div>
              <p className="text-xs uppercase text-slate-500">Tipo</p>
              <p className="mt-1 text-slate-700">{job.jobType}</p>
            </div>
            <div>
              <p className="text-xs uppercase text-slate-500">Criado em</p>
              <p className="mt-1 text-slate-700">{new Date(job.createdAt).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-xs uppercase text-slate-500">Atualizado em</p>
              <p className="mt-1 text-slate-700">{new Date(job.updatedAt).toLocaleString()}</p>
            </div>
          </section>

          <div className="grid gap-3 lg:grid-cols-2">
            <JsonViewer title="JSON de entrada" data={job.input} />
            <JsonViewer title="JSON de saída" data={job.output ?? {}} />
          </div>

          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="mb-2 text-sm font-semibold text-slate-700">Relatório markdown</h2>
            {job.reportMarkdown ? (
              <MarkdownRenderer markdown={job.reportMarkdown} />
            ) : (
              <p className="text-sm text-slate-500">Sem relatório markdown para este job.</p>
            )}
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-700">Evidências</h2>
            <EvidenceList evidence={job.evidence} />
            <div className="mt-3">
              <Link href={`/audit?job_id=${job.id}`} className="text-sm font-medium text-tribultz-700 hover:underline">
                Abrir auditoria relacionada
              </Link>
            </div>
          </section>
        </>
      )}

      {error ? <Toast message={error} tone="error" onClose={() => setError(null)} /> : null}
    </section>
  );
}
