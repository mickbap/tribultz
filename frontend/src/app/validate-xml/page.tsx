"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useMemo, useState } from "react";
import { Skeleton } from "@/components/common/Skeleton";
import { Toast } from "@/components/common/Toast";
import { getJob, openExceptionRequest, validateXml } from "@/lib/api";
import { Finding, Job, ValidateXmlRequest, ValidationEvidence, ValidationResultV11, XmlDocumentType } from "@/lib/types";

function severityClasses(severity: Finding["severity"]): string {
  if (severity === "FATAL") {
    return "border-red-300 bg-red-50 text-red-800";
  }
  return "border-amber-300 bg-amber-50 text-amber-800";
}

function severityLabel(severity: Finding["severity"]): string {
  return severity === "FATAL" ? "FATAL (bloqueante)" : "ALERT";
}

function shortSnippet(value?: string): string {
  if (!value) return "Sem trecho disponível.";
  return value.length > 300 ? `${value.slice(0, 297)}...` : value;
}

function validateInput(xml: string): string | null {
  if (!xml.trim()) return "Informe um XML para validar.";
  if (!xml.includes("<") || !xml.includes(">")) return "Conteúdo não parece XML válido.";
  return null;
}

export default function ValidateXmlPage() {
  const [documentType, setDocumentType] = useState<XmlDocumentType>("NFSE");
  const [xmlText, setXmlText] = useState("");
  const [source, setSource] = useState<"paste" | "upload">("paste");
  const [result, setResult] = useState<ValidationResultV11 | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);
  const [openingExceptionFor, setOpeningExceptionFor] = useState<Finding | null>(null);
  const [justification, setJustification] = useState("");
  const [toast, setToast] = useState<{ tone: "success" | "error" | "info"; msg: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const evidenceMap = useMemo(() => {
    const map = new Map<string, ValidationEvidence>();
    for (const ev of result?.evidences ?? []) {
      map.set(ev.id, ev);
    }
    return map;
  }, [result]);

  const fatalCount = useMemo(
    () => result?.findings.filter((f) => f.severity === "FATAL").length ?? 0,
    [result],
  );

  async function onFileChange(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setXmlText(text);
    setSource("upload");
  }

  async function refreshJob(jobId: string): Promise<void> {
    try {
      const next = await getJob(jobId);
      if (next) setJob(next);
    } catch {
      // best-effort status refresh
    }
  }

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);
    setToast(null);

    const validationError = validateInput(xmlText);
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    setResult(null);
    setJob(null);

    try {
      const payload: ValidateXmlRequest = {
        document_type: documentType,
        xml: xmlText,
        source,
      };
      const response = await validateXml(payload);
      setResult(response);
      await refreshJob(response.job.id);
      window.setTimeout(() => {
        void refreshJob(response.job.id);
      }, 2000);
      setToast({ tone: "success", msg: "Validação executada com sucesso." });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao validar XML.");
    } finally {
      setLoading(false);
    }
  }

  async function submitException(): Promise<void> {
    if (!result || !openingExceptionFor) return;
    if (!justification.trim()) {
      setToast({ tone: "error", msg: "Justificativa obrigatória para abrir exceção." });
      return;
    }
    try {
      await openExceptionRequest({
        job_id: result.job.id,
        finding_id: openingExceptionFor.id,
        rule_id: openingExceptionFor.rule_id,
        justification: justification.trim(),
        created_by: "operador.demo",
      });
      setOpeningExceptionFor(null);
      setJustification("");
      setToast({ tone: "success", msg: "Exceção aberta e enviada para fila do coordenador." });
      await refreshJob(result.job.id);
    } catch (err) {
      setToast({ tone: "error", msg: err instanceof Error ? err.message : "Falha ao abrir exceção." });
    }
  }

  function copySnippet(snippet?: string): void {
    if (!snippet) return;
    navigator.clipboard
      .writeText(snippet)
      .then(() => setToast({ tone: "info", msg: "Trecho copiado." }))
      .catch(() => setToast({ tone: "error", msg: "Não foi possível copiar o trecho." }));
  }

  return (
    <section className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Validar XML</h1>
        <p className="text-sm text-slate-500">
          NFS-e primeiro (NF-e suportado). Toda inconsistência gera finding com evidência rastreável.
        </p>
      </header>

      <form onSubmit={onSubmit} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4">
        <div className="grid gap-3 md:grid-cols-[14rem_1fr]">
          <label className="text-sm">
            <span className="mb-1 block text-slate-500">Tipo do documento</span>
            <select
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value as XmlDocumentType)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
            >
              <option value="NFSE">NFS-e</option>
              <option value="NFE">NF-e</option>
            </select>
          </label>

          <label className="text-sm">
            <span className="mb-1 block text-slate-500">Upload XML</span>
            <input
              type="file"
              accept=".xml,text/xml"
              onChange={(e) => void onFileChange(e)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </label>
        </div>

        <label className="block text-sm">
          <span className="mb-1 block text-slate-500">Cole o XML</span>
          <textarea
            value={xmlText}
            onChange={(e) => {
              setXmlText(e.target.value);
              setSource("paste");
            }}
            placeholder="<NFS-e>...</NFS-e>"
            className="min-h-56 w-full rounded-lg border border-slate-300 p-3 font-mono text-xs"
          />
        </label>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-tribultz-600 px-4 py-2 text-sm font-semibold text-white hover:bg-tribultz-700 disabled:opacity-70"
          >
            {loading ? "Validando..." : "Validar"}
          </button>
          {result ? (
            <>
              <Link href={`/jobs/${result.job.id}`} className="text-sm font-medium text-tribultz-700 hover:underline">
                Abrir Job
              </Link>
              <Link
                href={`/audit?job_id=${encodeURIComponent(result.job.id)}`}
                className="text-sm font-medium text-tribultz-700 hover:underline"
              >
                Abrir Audit
              </Link>
            </>
          ) : null}
        </div>
      </form>

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : null}

      {result ? (
        <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4">
          <div className={`rounded-lg border p-3 text-sm ${fatalCount > 0 ? "border-red-300 bg-red-50" : "border-emerald-300 bg-emerald-50"}`}>
            <p className="font-semibold">
              {fatalCount > 0
                ? `Bloqueio visual ativo: ${fatalCount} finding(s) FATAL.`
                : "Sem bloqueios FATAL. Exceções ALERT podem seguir com justificativa."}
            </p>
            <p className="text-xs text-slate-600">
              Job: <span className="font-mono">{result.job.id}</span> | Audit: <span className="font-mono">{result.audit.id}</span>
              {job ? ` | Status do job: ${job.status}` : ""}
            </p>
          </div>

          <div className="space-y-3">
            {result.findings.map((finding) => {
              const evidences = finding.evidence_ids.map((id) => evidenceMap.get(id)).filter(Boolean) as ValidationEvidence[];
              return (
                <article key={finding.id} className={`rounded-xl border p-3 ${severityClasses(finding.severity)}`}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide">{severityLabel(finding.severity)}</p>
                      <h2 className="text-base font-semibold">{finding.title}</h2>
                      <p className="text-xs">
                        rule_id: <span className="font-mono">{finding.rule_id}</span> | finding_id:{" "}
                        <span className="font-mono">{finding.id}</span>
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setOpeningExceptionFor(finding)}
                      className="rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                    >
                      Abrir exceção
                    </button>
                  </div>

                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <div className="rounded border border-slate-200 bg-white p-2 text-xs text-slate-700">
                      <p>
                        <span className="font-semibold">Campo:</span> {finding.where.field ?? "-"}
                      </p>
                      <p className="break-all">
                        <span className="font-semibold">XPath:</span> {finding.where.xpath ?? "-"}
                      </p>
                      <p className="font-semibold">Trecho:</p>
                      <pre className="scroll-thin max-h-28 overflow-auto rounded bg-slate-100 p-2 text-[11px]">
                        {shortSnippet(finding.where.snippet)}
                      </pre>
                    </div>
                    <div className="rounded border border-slate-200 bg-white p-2 text-xs text-slate-700">
                      <p className="font-semibold">Recomendação</p>
                      <p>{finding.recommendation}</p>
                    </div>
                  </div>

                  <div className="mt-3 space-y-2">
                    <p className="text-xs font-semibold">Evidências de fonte</p>
                    {evidences.length === 0 ? (
                      <p className="text-xs">Sem evidências vinculadas.</p>
                    ) : (
                      evidences.map((ev) => (
                        <div key={ev.id} className="rounded border border-slate-200 bg-white p-2 text-xs text-slate-700">
                          <p>
                            <span className="font-semibold">{ev.label}</span> ({ev.type}) [{ev.id}]
                          </p>
                          {ev.xpath ? <p className="break-all">XPath: {ev.xpath}</p> : null}
                          {ev.snippet ? (
                            <>
                              <pre className="scroll-thin mt-1 max-h-24 overflow-auto rounded bg-slate-100 p-2 text-[11px]">
                                {shortSnippet(ev.snippet)}
                              </pre>
                              <button
                                type="button"
                                onClick={() => copySnippet(ev.snippet)}
                                className="mt-1 rounded border border-slate-300 px-2 py-1 text-[11px] font-semibold hover:bg-slate-100"
                              >
                                Copiar snippet
                              </button>
                            </>
                          ) : null}
                          {ev.href ? (
                            <p className="mt-1">
                              <a className="text-tribultz-700 underline" href={ev.href}>
                                Abrir link de evidência
                              </a>
                            </p>
                          ) : null}
                        </div>
                      ))
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ) : null}

      {!loading && !result ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-500">
          Cole ou envie um XML e clique em Validar para gerar findings e evidências.
        </div>
      ) : null}

      {openingExceptionFor ? (
        <div className="fixed inset-0 z-40 bg-slate-900/40" role="dialog" aria-modal="true">
          <div className="mx-auto mt-12 w-[94%] max-w-xl rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
            <h3 className="text-lg font-semibold text-slate-900">Abrir exceção</h3>
            <p className="text-xs text-slate-500">
              finding_id <span className="font-mono">{openingExceptionFor.id}</span> | rule_id{" "}
              <span className="font-mono">{openingExceptionFor.rule_id}</span>
            </p>
            <label className="mt-3 block text-sm">
              <span className="mb-1 block text-slate-600">Justificativa (obrigatória)</span>
              <textarea
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
                className="min-h-24 w-full rounded-lg border border-slate-300 p-2 text-sm"
                placeholder="Descreva motivo, base legal e plano de correção."
              />
            </label>
            <div className="mt-3 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setOpeningExceptionFor(null);
                  setJustification("");
                }}
                className="rounded border border-slate-300 px-3 py-1.5 text-sm"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => void submitException()}
                className="rounded bg-tribultz-600 px-3 py-1.5 text-sm font-semibold text-white"
              >
                Enviar para aprovação
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {error ? <Toast message={error} tone="error" onClose={() => setError(null)} /> : null}
      {toast ? <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}
