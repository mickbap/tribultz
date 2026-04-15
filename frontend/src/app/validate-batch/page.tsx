"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Toast } from "@/components/common/Toast";
import { validateXml } from "@/lib/api";
import { canAccess } from "@/lib/plan";
import { buildBatchReportCsv, buildBatchReportHtml, downloadBatchCsv, downloadBatchPdf } from "@/lib/export/batchReport";
import { ValidateXmlRequest, ValidationResultV11, XmlDocumentType } from "@/lib/types";

type BatchItem = {
  filename: string;
  xml: string;
  status: "pending" | "validating" | "done" | "error";
  result?: ValidationResultV11;
  error?: string;
};

function statusLabel(status: BatchItem["status"]): string {
  switch (status) {
    case "pending":
      return "Aguardando";
    case "validating":
      return "Validando...";
    case "done":
      return "Concluído";
    case "error":
      return "Erro";
  }
}

function statusColor(status: BatchItem["status"]): string {
  switch (status) {
    case "pending":
      return "text-slate-500";
    case "validating":
      return "text-blue-600";
    case "done":
      return "text-emerald-600";
    case "error":
      return "text-red-600";
  }
}

function resultBadge(item: BatchItem): string {
  if (!item.result) return "-";
  const fatals = item.result.findings.filter((f) => f.severity === "FATAL").length;
  return fatals > 0 ? `FAIL (${fatals})` : "PASS";
}

function resultBadgeColor(item: BatchItem): string {
  if (!item.result) return "text-slate-400";
  const fatals = item.result.findings.filter((f) => f.severity === "FATAL").length;
  return fatals > 0 ? "text-red-600 font-semibold" : "text-emerald-600 font-semibold";
}

export default function ValidateBatchPage() {
  const router = useRouter();

  // Plan gate: only profissional, empresarial, contador, admin can access batch
  useEffect(() => {
    if (!canAccess("hasBatch")) {
      router.replace("/billing");
    }
  }, [router]);

  const [documentType, setDocumentType] = useState<XmlDocumentType>("NFSE");
  const [items, setItems] = useState<BatchItem[]>([]);
  const [running, setRunning] = useState(false);
  const [toast, setToast] = useState<{ tone: "success" | "error" | "info"; msg: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const completedResults = useMemo(() => {
    return items.filter((i) => i.status === "done" && i.result).map((i) => ({
      filename: i.filename,
      result: i.result!,
    }));
  }, [items]);

  const summary = useMemo(() => {
    const done = items.filter((i) => i.status === "done" && i.result);
    const pass = done.filter((i) => i.result!.findings.every((f) => f.severity !== "FATAL")).length;
    const fail = done.length - pass;
    const totalFindings = done.reduce((sum, i) => sum + i.result!.findings.length, 0);
    const totalFatal = done.reduce((sum, i) => sum + i.result!.findings.filter((f) => f.severity === "FATAL").length, 0);
    return { total: done.length, pass, fail, totalFindings, totalFatal };
  }, [items]);

  const progress = useMemo(() => {
    if (items.length === 0) return 0;
    const done = items.filter((i) => i.status === "done" || i.status === "error").length;
    return Math.round((done / items.length) * 100);
  }, [items]);

  function onFileChange(event: ChangeEvent<HTMLInputElement>): void {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const newItems: BatchItem[] = [];
    const readPromises: Promise<void>[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const idx = newItems.length;
      newItems.push({ filename: file.name, xml: "", status: "pending" });
      readPromises.push(
        file.text().then((text) => {
          newItems[idx].xml = text;
        }),
      );
    }

    void Promise.all(readPromises).then(() => {
      setItems((prev) => [...prev, ...newItems]);
    });

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function onDrop(event: React.DragEvent): void {
    event.preventDefault();
    const files = event.dataTransfer.files;
    if (!files || files.length === 0) return;

    const newItems: BatchItem[] = [];
    const readPromises: Promise<void>[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!file.name.toLowerCase().endsWith(".xml")) continue;
      const idx = newItems.length;
      newItems.push({ filename: file.name, xml: "", status: "pending" });
      readPromises.push(
        file.text().then((text) => {
          newItems[idx].xml = text;
        }),
      );
    }

    void Promise.all(readPromises).then(() => {
      if (newItems.length === 0) {
        setToast({ tone: "error", msg: "Nenhum arquivo .xml encontrado." });
        return;
      }
      setItems((prev) => [...prev, ...newItems]);
    });
  }

  function removeItem(index: number): void {
    setItems((prev) => prev.filter((_, i) => i !== index));
  }

  function clearAll(): void {
    setItems([]);
  }

  const runBatch = useCallback(async () => {
    const pendingItems = items.filter((i) => i.status === "pending");
    if (pendingItems.length === 0) {
      setToast({ tone: "info", msg: "Nenhum arquivo pendente para validar." });
      return;
    }

    setRunning(true);

    for (let i = 0; i < items.length; i++) {
      if (items[i].status !== "pending") continue;

      setItems((prev) =>
        prev.map((item, idx) => (idx === i ? { ...item, status: "validating" } : item)),
      );

      try {
        const payload: ValidateXmlRequest = {
          document_type: documentType,
          xml: items[i].xml,
          source: "upload",
        };
        const result = await validateXml(payload);
        setItems((prev) =>
          prev.map((item, idx) => (idx === i ? { ...item, status: "done", result } : item)),
        );
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Falha ao validar";
        setItems((prev) =>
          prev.map((item, idx) => (idx === i ? { ...item, status: "error", error: errorMsg } : item)),
        );
      }
    }

    setRunning(false);
    setToast({ tone: "success", msg: "Lote concluído." });
  }, [items, documentType]);

  return (
    <section className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Validar em Lote</h1>
        <p className="text-sm text-slate-500">
          Upload de múltiplos XMLs para validação sequencial com relatório consolidado.
        </p>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-4">
        <div className="flex flex-wrap items-end gap-4">
          <label className="text-sm">
            <span className="mb-1 block text-slate-500">Tipo do documento</span>
            <select
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value as XmlDocumentType)}
              className="w-48 rounded-lg border border-slate-300 px-3 py-2"
            >
              <option value="NFSE">NFS-e</option>
              <option value="NFE">NF-e</option>
            </select>
          </label>

          <label className="text-sm">
            <span className="mb-1 block text-slate-500">Selecionar XMLs</span>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xml,text/xml"
              multiple
              onChange={onFileChange}
              className="rounded-lg border border-slate-300 px-3 py-2"
            />
          </label>
        </div>

        <div
          onDrop={onDrop}
          onDragOver={(e) => e.preventDefault()}
          className="flex min-h-24 items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500"
        >
          Arraste arquivos .xml aqui ou use o seletor acima
        </div>

        {items.length > 0 && (
          <>
            {running && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-slate-600">
                  <span>Progresso</span>
                  <span>{progress}%</span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-200">
                  <div
                    className="h-2 rounded-full bg-tribultz-600 transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                    <th className="px-3 py-2">#</th>
                    <th className="px-3 py-2">Arquivo</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Resultado</th>
                    <th className="px-3 py-2">Findings</th>
                    <th className="px-3 py-2">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, idx) => (
                    <tr key={idx} className="border-b border-slate-100">
                      <td className="px-3 py-2 text-slate-400">{idx + 1}</td>
                      <td className="px-3 py-2 font-mono text-xs">{item.filename}</td>
                      <td className={`px-3 py-2 text-xs ${statusColor(item.status)}`}>
                        {statusLabel(item.status)}
                      </td>
                      <td className={`px-3 py-2 text-xs ${resultBadgeColor(item)}`}>
                        {resultBadge(item)}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {item.result ? item.result.findings.length : item.error ? item.error : "-"}
                      </td>
                      <td className="px-3 py-2">
                        {item.result && (
                          <Link
                            href={`/jobs/${item.result.job.id}`}
                            className="text-xs text-tribultz-700 hover:underline"
                          >
                            Ver Job
                          </Link>
                        )}
                        {!running && item.status === "pending" && (
                          <button
                            type="button"
                            onClick={() => removeItem(idx)}
                            className="text-xs text-red-500 hover:underline"
                          >
                            Remover
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {summary.total > 0 && (
              <div className="grid gap-3 md:grid-cols-4">
                <div className="rounded-lg border border-slate-200 p-3 text-center">
                  <p className="text-xs uppercase text-slate-500">Total</p>
                  <p className="text-xl font-bold">{summary.total}</p>
                </div>
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-center">
                  <p className="text-xs uppercase text-emerald-600">PASS</p>
                  <p className="text-xl font-bold text-emerald-700">{summary.pass}</p>
                </div>
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-center">
                  <p className="text-xs uppercase text-red-600">FAIL</p>
                  <p className="text-xl font-bold text-red-700">{summary.fail}</p>
                </div>
                <div className="rounded-lg border border-slate-200 p-3 text-center">
                  <p className="text-xs uppercase text-slate-500">Findings</p>
                  <p className="text-xl font-bold">{summary.totalFindings}</p>
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void runBatch()}
                disabled={running || items.every((i) => i.status !== "pending")}
                className="rounded-lg bg-tribultz-600 px-4 py-2 text-sm font-semibold text-white hover:bg-tribultz-700 disabled:opacity-70"
              >
                {running ? "Processando..." : "Validar Lote"}
              </button>

              {completedResults.length > 0 && (
                <>
                  <button
                    type="button"
                    onClick={() => downloadBatchCsv(buildBatchReportCsv(completedResults, documentType), "lote")}
                    className="rounded border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  >
                    Exportar CSV
                  </button>
                  <button
                    type="button"
                    onClick={() => downloadBatchPdf(buildBatchReportHtml(completedResults, documentType), "lote")}
                    className="rounded border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  >
                    Exportar PDF
                  </button>
                </>
              )}

              <button
                type="button"
                onClick={clearAll}
                disabled={running}
                className="rounded border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-500 hover:bg-slate-100 disabled:opacity-50"
              >
                Limpar
              </button>
            </div>
          </>
        )}
      </div>

      {toast ? <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}
