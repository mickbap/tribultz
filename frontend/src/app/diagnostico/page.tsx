"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { API_BASE, createTransactionId } from "@/lib/api";
import { RULES_COUNT } from "@/lib/validation/rulesMeta";

// ── Types ────────────────────────────────────────────────────────────────────

type FindingSummary = {
  rule_id: string;
  severity: string;
  title: string;
};

type DiagnosticResult = {
  document_type: string;
  status: string;
  total_findings: number;
  findings_shown: number;
  findings_hidden: number;
  fatals: number;
  alerts: number;
  findings: FindingSummary[];
  rules_checked: number;
  upgrade_cta: string;
  data_policy: string;
  transaction_id?: string;
};

type UploadState = "idle" | "uploading" | "done" | "error";

// ── Component ────────────────────────────────────────────────────────────────

export default function DiagnosticoPage() {
  const [state, setState] = useState<UploadState>("idle");
  const [result, setResult] = useState<DiagnosticResult | null>(null);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);

  const handleFile = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".xml")) {
      setError("Apenas arquivos .xml são aceitos.");
      setState("error");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError("Arquivo excede 2MB.");
      setState("error");
      return;
    }

    setState("uploading");
    setError("");
    setResult(null);

    try {
      const transactionId = createTransactionId();
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${API_BASE}/api/v1/public/validate`, {
        method: "POST",
        headers: { "X-Transaction-Id": transactionId },
        body: formData,
      });

      if (res.status === 429) {
        setError("Limite de requisições atingido. Aguarde 1 minuto e tente novamente.");
        setState("error");
        return;
      }

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "Erro ao validar" }));
        setError(body.detail ?? `Erro ${res.status}`);
        setState("error");
        return;
      }

      const data: DiagnosticResult = await res.json();
      setResult({
        ...data,
        transaction_id: data.transaction_id ?? transactionId,
      });
      setState("done");
    } catch {
      setError("Erro de conexão. Verifique se o servidor está acessível.");
      setState("error");
    }
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const onFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  return (
    <>
      {/* Hero */}
      <section className="bg-gradient-to-br from-tribultz-50 to-white px-4 py-16 text-center md:py-24">
        <h1 className="mx-auto max-w-3xl text-3xl font-extrabold text-slate-900 md:text-4xl">
          Sua NF-e está em conformidade com IBS/CBS?
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-600">
          A multa por não destacar IBS e CBS pode chegar a{" "}
          <strong className="text-red-600">18% do valor da operação</strong>.
          Faça o diagnóstico gratuito agora.
        </p>
        <div className="mx-auto mt-2 flex items-center justify-center gap-4 text-sm text-slate-500">
          <span>{RULES_COUNT} regras verificadas</span>
          <span>NF-e, NFC-e e NFS-e</span>
          <span>NT 2025.002-RTC</span>
        </div>
      </section>

      {/* Upload area */}
      <section className="mx-auto -mt-8 max-w-2xl px-4 pb-16">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          className={`rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
            dragOver
              ? "border-tribultz-500 bg-tribultz-50"
              : "border-slate-300 bg-white hover:border-tribultz-400"
          }`}
        >
          {state === "uploading" ? (
            <div className="flex flex-col items-center gap-3">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-tribultz-200 border-t-tribultz-600" />
              <p className="text-sm text-slate-600">Validando XML...</p>
            </div>
          ) : (
            <>
              <svg
                className="mx-auto h-12 w-12 text-slate-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                />
              </svg>
              <p className="mt-4 text-base font-medium text-slate-700">
                Arraste seu arquivo XML aqui
              </p>
              <p className="mt-1 text-sm text-slate-500">ou</p>
              <label className="mt-3 inline-block cursor-pointer rounded-lg bg-tribultz-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-tribultz-700">
                Selecionar arquivo
                <input
                  type="file"
                  accept=".xml"
                  className="hidden"
                  onChange={onFileSelect}
                />
              </label>
              <p className="mt-3 text-xs text-slate-400">
                NF-e, NFC-e ou NFS-e — até 2MB
              </p>
            </>
          )}
        </div>

        {/* Error */}
        {state === "error" && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Results */}
        {state === "done" && result && (
          <div className="mt-6 space-y-4">
            {/* Status badge */}
            <div
              className={`flex items-center justify-between rounded-xl border p-5 ${
                result.status === "PASS"
                  ? "border-emerald-200 bg-emerald-50"
                  : "border-red-200 bg-red-50"
              }`}
            >
              <div>
                <h2 className="text-lg font-bold">
                  {result.status === "PASS" ? (
                    <span className="text-emerald-700">Conformidade OK</span>
                  ) : (
                    <span className="text-red-700">Problemas Encontrados</span>
                  )}
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                  Documento: <strong>{result.document_type}</strong> &middot;{" "}
                  {result.rules_checked} regras verificadas
                </p>
                {result.transaction_id ? (
                  <p className="mt-1 text-xs text-slate-500">Tx: {result.transaction_id}</p>
                ) : null}
              </div>
              <div className="text-right">
                <div className="text-3xl font-extrabold">
                  {result.status === "PASS" ? (
                    <span className="text-emerald-600">0</span>
                  ) : (
                    <span className="text-red-600">{result.total_findings}</span>
                  )}
                </div>
                <p className="text-xs text-slate-500">
                  {result.total_findings === 1 ? "problema" : "problemas"}
                </p>
              </div>
            </div>

            {/* Severity breakdown */}
            {result.total_findings > 0 && (
              <div className="flex gap-3">
                {result.fatals > 0 && (
                  <span className="rounded-full bg-red-100 px-3 py-1 text-sm font-semibold text-red-700">
                    {result.fatals} {result.fatals === 1 ? "erro crítico" : "erros críticos"}
                  </span>
                )}
                {result.alerts > 0 && (
                  <span className="rounded-full bg-amber-100 px-3 py-1 text-sm font-semibold text-amber-700">
                    {result.alerts} {result.alerts === 1 ? "alerta" : "alertas"}
                  </span>
                )}
              </div>
            )}

            {/* Findings list */}
            {result.findings.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white">
                <div className="border-b border-slate-200 px-4 py-3">
                  <h3 className="text-sm font-semibold text-slate-700">
                    Regras com problema
                  </h3>
                </div>
                <ul className="divide-y divide-slate-100">
                  {result.findings.map((f, i) => (
                    <li key={i} className="flex items-start gap-3 px-4 py-3">
                      <span
                        className={`mt-0.5 inline-block h-2 w-2 flex-shrink-0 rounded-full ${
                          f.severity === "FATAL" ? "bg-red-500" : "bg-amber-500"
                        }`}
                      />
                      <div>
                        <p className="text-sm font-medium text-slate-800">{f.title}</p>
                        <p className="text-xs text-slate-500">
                          Regra: {f.rule_id} &middot; {f.severity}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Hidden findings indicator */}
            {result.findings_hidden > 0 && (
              <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
                <svg className="h-5 w-5 flex-shrink-0 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
                <p className="text-sm text-amber-800">
                  Exibindo <strong>{result.findings_shown}</strong> de{" "}
                  <strong>{result.total_findings}</strong> problemas encontrados.{" "}
                  <strong>{result.findings_hidden}</strong>{" "}
                  {result.findings_hidden === 1
                    ? "problema adicional oculto"
                    : "problemas adicionais ocultos"}{" "}
                  no diagnóstico gratuito.
                </p>
              </div>
            )}

            {/* Blurred CTA section */}
            <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white">
              {/* Blurred fake content */}
              <div className="pointer-events-none select-none px-4 py-4 blur-sm">
                <p className="text-sm text-slate-600">
                  Evidência XML: /nfeProc/NFe/infNFe/det/imposto/IBSCBS/CST
                </p>
                <p className="text-sm text-slate-600">
                  Recomendação: Corrigir no ERP conforme NT 2025.002-RTC e reemitir a nota.
                </p>
                <p className="text-sm text-slate-600">
                  Snippet: &lt;CST&gt;999&lt;/CST&gt; — código não reconhecido
                </p>
              </div>
              {/* Overlay CTA */}
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 backdrop-blur-[2px]">
                <svg
                  className="h-8 w-8 text-tribultz-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
                  />
                </svg>
                <p className="mt-2 text-sm font-semibold text-slate-700">
                  {result.upgrade_cta}
                </p>
                <div className="mt-3 flex gap-3">
                  <Link
                    href="/register"
                    className="rounded-lg bg-tribultz-600 px-5 py-2 text-sm font-semibold text-white hover:bg-tribultz-700"
                  >
                    Criar conta gratuita
                  </Link>
                  <Link
                    href="/login"
                    className="rounded-lg border border-slate-300 px-5 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                  >
                    Já tenho conta
                  </Link>
                </div>
              </div>
            </div>

            {/* Data governance notice */}
            <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
              <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
              <div>
                <p className="text-sm font-medium text-emerald-800">Seus dados estão seguros</p>
                <p className="mt-0.5 text-xs text-emerald-700">{result.data_policy}</p>
              </div>
            </div>

            {/* Try again */}
            <div className="text-center">
              <button
                type="button"
                onClick={() => {
                  setState("idle");
                  setResult(null);
                }}
                className="text-sm font-medium text-tribultz-600 hover:text-tribultz-700"
              >
                Validar outro XML
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Data governance */}
      <section className="border-t border-slate-200 bg-white px-4 py-10">
        <div className="mx-auto max-w-4xl rounded-xl border border-tribultz-100 bg-tribultz-50 p-5">
          <h3 className="text-base font-semibold text-slate-900">Compromisso com governança de dados</h3>
          <p className="mt-2 text-sm text-slate-700">
            O XML enviado no freemium é processado apenas para gerar o diagnóstico técnico de conformidade.
            Não utilizamos os dados fiscais para treino de modelos e o conteúdo é descartado após a análise.
          </p>
        </div>
      </section>

      {/* Social proof / urgency */}
      <section className="border-t border-slate-200 bg-slate-50 px-4 py-12">
        <div className="mx-auto grid max-w-4xl gap-8 md:grid-cols-3">
          <div className="text-center">
            <p className="text-3xl font-extrabold text-red-600">80%</p>
            <p className="mt-1 text-sm text-slate-600">
              das empresas ainda não parametrizaram IBS/CBS nas notas fiscais
            </p>
          </div>
          <div className="text-center">
            <p className="text-3xl font-extrabold text-red-600">18%</p>
            <p className="mt-1 text-sm text-slate-600">
              do valor da operação em multa por não destacar IBS e CBS
            </p>
          </div>
          <div className="text-center">
            <p className="text-3xl font-extrabold text-tribultz-600">{RULES_COUNT}</p>
            <p className="mt-1 text-sm text-slate-600">
              regras fiscais verificadas conforme NT 2025.002-RTC
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
