"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Skeleton } from "@/components/common/Skeleton";
import { Toast } from "@/components/common/Toast";
import { ErpFormat, getSpedCsv, getSpedErpExport, getSpedRun, SpedRunResponse, uploadSped } from "@/lib/api";

type UploadState = "idle" | "uploading" | "polling" | "done" | "error";

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    PENDING: "bg-slate-100 text-slate-600",
    RUNNING: "bg-blue-100 text-blue-700",
    SUCCESS: "bg-emerald-100 text-emerald-700",
    FAILED: "bg-red-100 text-red-700",
  };
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${map[status] ?? "bg-slate-100 text-slate-500"}`}>
      {status}
    </span>
  );
}

function ScoreGauge({ pct }: { pct: number }) {
  const color = pct >= 90 ? "text-emerald-600" : pct >= 70 ? "text-amber-500" : "text-red-600";
  return (
    <div className="flex flex-col items-center">
      <span className={`text-4xl font-bold tabular-nums ${color}`}>{pct.toFixed(1)}%</span>
      <span className="mt-1 text-xs text-slate-500">Conformidade</span>
    </div>
  );
}

export default function ValidateSpedPage() {
  const [state, setState] = useState<UploadState>("idle");
  const [run, setRun] = useState<SpedRunResponse | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [erpOpen, setErpOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const erpRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!erpOpen) return;
    function close(e: MouseEvent) {
      if (erpRef.current && !erpRef.current.contains(e.target as Node)) setErpOpen(false);
    }
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [erpOpen]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const startPolling = useCallback((runId: string) => {
    setState("polling");
    pollRef.current = setInterval(async () => {
      try {
        const data = await getSpedRun(runId);
        setRun(data);
        if (data.status === "SUCCESS" || data.status === "FAILED") {
          stopPolling();
          setState(data.status === "SUCCESS" ? "done" : "error");
          if (data.status === "FAILED") setError("Processamento falhou. Verifique o arquivo e tente novamente.");
        }
      } catch {
        stopPolling();
        setState("error");
        setError("Erro ao verificar status do processamento.");
      }
    }, 3000);
  }, [stopPolling]);

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith(".txt")) {
      setError("Apenas arquivos .txt (SPED Fiscal) são aceitos.");
      return;
    }
    setError(null);
    setRun(null);
    setState("uploading");
    try {
      const resp = await uploadSped(file);
      startPolling(resp.sped_run_id);
    } catch (e) {
      setState("error");
      setError((e as Error).message ?? "Erro no upload.");
    }
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  async function downloadCsv() {
    if (!run) return;
    try {
      const csv = await getSpedCsv(run.id);
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sped-resultados-${run.id.slice(0, 8)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Não foi possível baixar o CSV.");
    }
  }

  const ERP_OPTIONS: { value: ErpFormat; label: string }[] = [
    { value: "totvs",   label: "TOTVS Protheus" },
    { value: "sap",     label: "SAP Business One" },
    { value: "omie",    label: "Omie" },
    { value: "linx",    label: "Linx" },
    { value: "generic", label: "Genérico (CSV)" },
  ];

  async function downloadErp(fmt: ErpFormat) {
    if (!run) return;
    setErpOpen(false);
    try {
      const blob = await getSpedErpExport(run.id, fmt);
      const opt = ERP_OPTIONS.find((o) => o.value === fmt);
      const ext = fmt === "linx" ? "txt" : "csv";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `tribultz_sped_${run.id.slice(0, 8)}_${fmt}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Não foi possível exportar para o ERP selecionado.");
    }
  }

  const scoreTotal = run?.total_produtos ?? 0;
  const scoreConformes = run?.produtos_conformes ?? 0;
  const scorePct = scoreTotal > 0 ? (scoreConformes / scoreTotal) * 100 : 0;

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">SPED Fiscal</h1>
        <p className="text-sm text-slate-500">
          Envie o arquivo EFD-ICMS/IPI e valide o catálogo de produtos contra as regras CBS/IBS da LC 214.
        </p>
      </header>

      {/* Drop zone */}
      <div
        className={`flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-10 transition-colors ${
          dragOver
            ? "border-tribultz-600 bg-tribultz-100"
            : "border-slate-300 bg-slate-50 hover:border-tribultz-400"
        } ${state === "uploading" || state === "polling" ? "opacity-60 pointer-events-none" : "cursor-pointer"}`}
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <input ref={fileRef} type="file" accept=".txt" className="hidden" onChange={onInputChange} />
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-tribultz-100 text-tribultz-600 text-2xl mb-3">
          ↑
        </div>
        {state === "idle" || state === "done" || state === "error" ? (
          <>
            <p className="text-sm font-semibold text-slate-700">Arraste o arquivo ou clique para selecionar</p>
            <p className="mt-1 text-xs text-slate-500">Somente .txt — até 100 MB</p>
          </>
        ) : state === "uploading" ? (
          <p className="text-sm font-semibold text-tribultz-700">Enviando arquivo…</p>
        ) : (
          <p className="text-sm font-semibold text-tribultz-700">Processando… aguarde.</p>
        )}
      </div>

      {/* Polling progress */}
      {state === "polling" && (
        <div className="space-y-2">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      )}

      {/* Results */}
      {run && (state === "done" || state === "polling") && (
        <div className="space-y-4">
          {/* Header card */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-semibold text-slate-800">{run.original_filename}</h2>
                  <StatusPill status={run.status} />
                </div>
                {run.cnpj_empresa && (
                  <p className="text-xs text-slate-500">
                    {run.nome_empresa ?? ""} — CNPJ {run.cnpj_empresa}
                  </p>
                )}
                {run.periodo_ini && (
                  <p className="text-xs text-slate-500">
                    Período: {run.periodo_ini} → {run.periodo_fim ?? "?"}
                  </p>
                )}
              </div>
              {state === "done" && <ScoreGauge pct={scorePct} />}
            </div>
          </div>

          {/* Metrics */}
          {state === "done" && (
            <div className="grid grid-cols-3 gap-3">
              <article className="rounded-xl border border-slate-200 bg-white p-4 text-center">
                <p className="text-xs uppercase text-slate-500">Total produtos</p>
                <p className="mt-1 text-2xl font-bold">{run.total_produtos}</p>
              </article>
              <article className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-center">
                <p className="text-xs uppercase text-emerald-600">Conformes</p>
                <p className="mt-1 text-2xl font-bold text-emerald-700">{run.produtos_conformes}</p>
              </article>
              <article className="rounded-xl border border-red-200 bg-red-50 p-4 text-center">
                <p className="text-xs uppercase text-red-500">Divergentes</p>
                <p className="mt-1 text-2xl font-bold text-red-600">{run.produtos_divergentes}</p>
              </article>
            </div>
          )}

          {/* Export buttons */}
          {state === "done" && run.status === "SUCCESS" && (
            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={downloadCsv}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
              >
                CSV Genérico
              </button>

              {/* ERP dropdown */}
              <div ref={erpRef} className="relative">
                <button
                  type="button"
                  onClick={() => setErpOpen((o) => !o)}
                  className="flex items-center gap-1.5 rounded-lg bg-tribultz-600 px-4 py-2 text-sm font-semibold text-white hover:bg-tribultz-700 transition-colors"
                >
                  Exportar para ERP
                  <svg className={`h-4 w-4 transition-transform ${erpOpen ? "rotate-180" : ""}`} viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                  </svg>
                </button>

                {erpOpen && (
                  <div className="absolute right-0 z-10 mt-1 w-48 rounded-xl border border-slate-200 bg-white py-1 shadow-lg">
                    {ERP_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => downloadErp(opt.value)}
                        className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {error && <Toast message={error} tone="error" onClose={() => setError(null)} />}
    </section>
  );
}
