"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { EvidenceList } from "@/components/common/EvidenceList";
import { JsonViewer } from "@/components/common/JsonViewer";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { Skeleton } from "@/components/common/Skeleton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Toast } from "@/components/common/Toast";
import { RegimeComparison } from "@/components/jobs/RegimeComparison";
import { getDocumentDownloadUrl, getJob, listDocuments } from "@/lib/api";
import type { DocumentResponse } from "@/lib/api";
import { exportEvidenceZipAndDownload } from "@/lib/export/evidenceExportUi";
import { Job, Finding } from "@/lib/types";

/**
 * JustificativaPanel — dados fornecidos pelo servidor (gate de plano server-side).
 * Não usa fiscalJustification.ts nem isPlanAtLeast() — a decisão de expor
 * os dados é tomada exclusivamente no backend ao retornar GET /api/v1/jobs/{id}.
 */
function JustificativaPanel({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false);

  // Gate resolvido server-side: se justification_gated=true, servidor sinalizou que
  // o plano atual não tem acesso mas existe justificativa para esta regra.
  if (finding.justification_gated) {
    return (
      <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
        <span className="font-semibold">Justificativa técnica + base legal</span> disponível a partir do plano{" "}
        <span className="font-semibold">Profissional</span>.{" "}
        <Link href="/billing" className="underline hover:text-amber-900">
          Fazer upgrade →
        </Link>
      </div>
    );
  }

  if (!finding.justification) return null;

  const j = finding.justification;

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs font-medium text-tribultz-700 hover:underline"
        aria-expanded={open}
      >
        <span>{open ? "▾" : "▸"}</span>
        Justificativa técnica e base legal
      </button>
      {open ? (
        <dl className="mt-2 space-y-2 rounded-lg border border-tribultz-100 bg-tribultz-50 px-3 py-3 text-xs text-slate-700">
          <div>
            <dt className="font-semibold text-tribultz-800">Base legal</dt>
            <dd className="mt-0.5 text-slate-600">{j.base_legal}</dd>
          </div>
          <div>
            <dt className="font-semibold text-tribultz-800">Por que essa regra existe</dt>
            <dd className="mt-0.5 leading-5 text-slate-600">{j.explicacao}</dd>
          </div>
          <div>
            <dt className="font-semibold text-tribultz-800">Correção recomendada</dt>
            <dd className="mt-0.5 leading-5 text-slate-600">{j.correcao}</dd>
          </div>
        </dl>
      ) : null}
    </div>
  );
}

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [toast, setToast] = useState<{ tone: "success" | "error" | "info"; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [derivedDocs, setDerivedDocs] = useState<DocumentResponse[]>([]);

  useEffect(() => {
    if (!params.id) return;
    setLoading(true);
    getJob(params.id)
      .then(setJob)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [params.id]);

  useEffect(() => {
    let cancelled = false;
    async function loadDerived(): Promise<void> {
      if (!job?.id) return;
      const docs = await listDocuments({ doc_type: "other", limit: 50 });
      const filtered = docs.filter((d) => {
        const fm = (d.fiscal_metadata || {}) as Record<string, unknown>;
        return fm["artifact_kind"] === "corrected_xml" && fm["source_job_id"] === job.id;
      });
      if (!cancelled) setDerivedDocs(filtered);
    }
    void loadDerived();
    return () => {
      cancelled = true;
    };
  }, [job?.id]);

  async function exportEvidenceBundle(): Promise<void> {
    if (!job || exporting) return;
    setExporting(true);
    const feedback = await exportEvidenceZipAndDownload(job.id);
    setToast(feedback);
    setExporting(false);
  }

  async function downloadCorrectedXml(documentId: string): Promise<void> {
    const { download_url } = await getDocumentDownloadUrl(documentId);
    window.open(download_url, "_blank", "noopener,noreferrer");
  }

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Detalhe do Job</h1>
          <p className="text-sm text-slate-500">Inspeção completa de entrada, saída e trilha de evidências.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={!job || loading || exporting}
            onClick={() => void exportEvidenceBundle()}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {exporting ? "Exportando…" : "Exportar evidências"}
          </button>
          {job ? <StatusBadge status={job.status} /> : null}
        </div>
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

          {job.output?.regime_comparison ? (
            <RegimeComparison data={job.output.regime_comparison as Record<string, string | null>} />
          ) : null}

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

          {job.findings?.length ? (
            <section className="rounded-xl border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-semibold text-slate-700">
                Findings da validação
                <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-normal text-slate-500">
                  {job.findings.length}
                </span>
              </h2>
              <ul className="space-y-3">
                {job.findings.map((finding) => (
                  <li
                    key={finding.id}
                    className={`rounded-lg border p-3 text-sm ${
                      finding.severity === "FATAL"
                        ? "border-red-200 bg-red-50"
                        : "border-amber-200 bg-amber-50"
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-bold tracking-wide ${
                          finding.severity === "FATAL"
                            ? "bg-red-100 text-red-700"
                            : "bg-amber-100 text-amber-700"
                        }`}
                      >
                        {finding.severity}
                      </span>
                      <span className="font-semibold text-slate-800">{finding.title}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      Regra: <code className="font-mono">{finding.rule_id}</code>
                    </p>
                    {finding.recommendation ? (
                      <p className="mt-1 text-xs text-slate-600">{finding.recommendation}</p>
                    ) : null}
                    <JustificativaPanel finding={finding} />
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {derivedDocs.length ? (
            <section className="rounded-xl border border-slate-200 bg-white p-4">
              <h2 className="mb-2 text-sm font-semibold text-slate-700">Artefatos derivados</h2>
              <ul className="space-y-2">
                {derivedDocs.map((doc) => (
                  <li key={doc.id} className="flex items-center justify-between rounded border border-slate-200 p-2 text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-800">
                        XML corrigido — {doc.original_filename ?? doc.storage_key.split("/").pop()}
                      </p>
                      <p className="text-xs text-slate-500">Criado em: {new Date(doc.created_at).toLocaleString()}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void downloadCorrectedXml(doc.id)}
                      className="ml-3 shrink-0 rounded border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                    >
                      Baixar XML corrigido
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-700">Evidências</h2>
            <EvidenceList evidence={job.evidence} />
            <div className="mt-3 flex flex-wrap gap-4">
              <Link href={`/audit?job_id=${job.id}`} className="text-sm font-medium text-tribultz-700 hover:underline">
                Abrir auditoria relacionada
              </Link>
              <Link href="/exceptions" className="text-sm font-medium text-tribultz-700 hover:underline">
                Abrir fila de exceções
              </Link>
            </div>
          </section>
        </>
      )}

      {error ? <Toast message={error} tone="error" onClose={() => setError(null)} /> : null}
      {toast ? <Toast message={toast.message} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}
