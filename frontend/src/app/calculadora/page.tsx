"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { API_BASE, createTransactionId } from "@/lib/api";
import { UF_LIST } from "@/lib/data/ufList";
import { CST_LIST } from "@/lib/data/cstList";

// ── Types ────────────────────────────────────────────────────────────────────

type CalculadoraResult = {
  vBC: string;
  pCBS: string;
  vCBS: string;
  pIBSUF: string;
  vIBSUF: string;
  pIBSMun: string;
  vIBSMun: string;
  vIBS: string;
  total_tributos: string;
  aliquota_efetiva: string;
  rate_source: string;
  cst: string;
  cst_desc: string;
  xml_snippet: string;
  data_policy: string;
  upgrade_cta: string;
  transaction_id?: string;
};

type CalcState = "idle" | "loading" | "done" | "error";

// ── Component ────────────────────────────────────────────────────────────────

function CalculadoraInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [uf, setUf] = useState(searchParams.get("uf") ?? "SP");
  const [baseValue, setBaseValue] = useState(searchParams.get("vBC") ?? "1000.00");
  const [ncm, setNcm] = useState(searchParams.get("ncm") ?? "");
  const [cst, setCst] = useState(searchParams.get("cst") ?? "000");
  const [quantity, setQuantity] = useState(searchParams.get("qty") ?? "1");

  const [state, setState] = useState<CalcState>("idle");
  const [result, setResult] = useState<CalculadoraResult | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const handleCalculate = useCallback(async () => {
    setState("loading");
    setError("");
    setResult(null);

    try {
      const transactionId = createTransactionId();
      const body: Record<string, string> = {
        uf_destino: uf,
        base_value: baseValue,
        quantity,
        cst,
      };
      if (ncm.trim()) body.ncm_code = ncm.trim();

      const res = await fetch(`${API_BASE}/api/v1/public/calculadora/regime-geral`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Transaction-Id": transactionId,
        },
        body: JSON.stringify(body),
      });

      if (res.status === 429) {
        setError("Limite de requisições atingido. Aguarde 1 minuto.");
        setState("error");
        return;
      }

      if (res.status === 422) {
        const detail = await res.json().catch(() => ({ detail: "Dados inválidos" }));
        const msg = Array.isArray(detail.detail)
          ? detail.detail.map((d: { msg: string }) => d.msg).join("; ")
          : detail.detail ?? "Dados inválidos";
        setError(msg);
        setState("error");
        return;
      }

      if (!res.ok) {
        setError(`Erro ${res.status}`);
        setState("error");
        return;
      }

      const data: CalculadoraResult = await res.json();
      setResult({
        ...data,
        transaction_id: data.transaction_id ?? transactionId,
      });
      setState("done");

      // Update URL params for sharing
      const params = new URLSearchParams();
      params.set("uf", uf);
      params.set("vBC", baseValue);
      if (ncm.trim()) params.set("ncm", ncm.trim());
      if (cst !== "000") params.set("cst", cst);
      if (quantity !== "1") params.set("qty", quantity);
      router.replace(`/calculadora?${params.toString()}`, { scroll: false });
    } catch {
      setError("Erro de conexão. Verifique se o servidor está acessível.");
      setState("error");
    }
  }, [uf, baseValue, ncm, cst, quantity, router]);

  const copyXml = useCallback(() => {
    if (result?.xml_snippet) {
      navigator.clipboard.writeText(result.xml_snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [result]);

  const copyShareUrl = useCallback(() => {
    navigator.clipboard.writeText(window.location.href);
  }, []);

  // Auto-calculate if URL has params on mount
  useEffect(() => {
    if (searchParams.get("vBC") && searchParams.get("uf")) {
      handleCalculate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pctFmt = (v: string) => `${(parseFloat(v) * 100).toFixed(2)}%`;
  const brlFmt = (v: string) => `R$ ${parseFloat(v).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;

  return (
    <>
      {/* Hero */}
      <section className="bg-gradient-to-br from-tribultz-50 to-white px-4 py-16 text-center md:py-20">
        <h1 className="mx-auto max-w-3xl text-3xl font-extrabold text-slate-900 md:text-4xl">
          Calculadora CBS/IBS
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-600">
          Calcule os tributos da Reforma Tributária para qualquer operação.
          Gere o XML <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-sm">&lt;IBSCBS&gt;</code> pronto para o ERP.
        </p>
        <div className="mx-auto mt-2 flex items-center justify-center gap-4 text-sm text-slate-500">
          <span>LC 214/2025</span>
          <span>NT 2025.002-RTC</span>
          <span>27 UFs</span>
        </div>
      </section>

      {/* Calculator form */}
      <section className="mx-auto -mt-6 max-w-2xl px-4 pb-16">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="grid gap-4 md:grid-cols-2">
            {/* UF */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                UF Destino *
              </label>
              <select
                value={uf}
                onChange={(e) => setUf(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-tribultz-500 focus:outline-none focus:ring-1 focus:ring-tribultz-500"
              >
                {UF_LIST.map((u) => (
                  <option key={u.code} value={u.code}>
                    {u.code} — {u.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Base Value */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Valor Base (R$) *
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={baseValue}
                onChange={(e) => setBaseValue(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-tribultz-500 focus:outline-none focus:ring-1 focus:ring-tribultz-500"
                placeholder="1000.00"
              />
            </div>

            {/* NCM */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                NCM <span className="text-slate-400">(opcional)</span>
              </label>
              <input
                type="text"
                maxLength={8}
                value={ncm}
                onChange={(e) => setNcm(e.target.value.replace(/\D/g, ""))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-tribultz-500 focus:outline-none focus:ring-1 focus:ring-tribultz-500"
                placeholder="84713012"
              />
              <p className="mt-0.5 text-xs text-slate-400">8 dígitos — alíquota reduzida para alimentos, pharma, educação</p>
            </div>

            {/* CST */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                CST
              </label>
              <select
                value={cst}
                onChange={(e) => setCst(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-tribultz-500 focus:outline-none focus:ring-1 focus:ring-tribultz-500"
              >
                {CST_LIST.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.code} — {c.desc}
                  </option>
                ))}
              </select>
            </div>

            {/* Quantity */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Quantidade
              </label>
              <input
                type="number"
                step="1"
                min="1"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-tribultz-500 focus:outline-none focus:ring-1 focus:ring-tribultz-500"
                placeholder="1"
              />
            </div>
          </div>

          {/* Calculate button */}
          <div className="mt-6 text-center">
            <button
              type="button"
              onClick={handleCalculate}
              disabled={state === "loading"}
              className="rounded-lg bg-tribultz-600 px-8 py-3 text-sm font-semibold text-white hover:bg-tribultz-700 disabled:opacity-50"
            >
              {state === "loading" ? "Calculando..." : "Calcular CBS/IBS"}
            </button>
          </div>
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
            {/* Breakdown card */}
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="text-base font-semibold text-slate-900">Resultado do Cálculo</h2>
              <p className="mt-1 text-xs text-slate-500">
                CST {result.cst} — {result.cst_desc} | Fonte: {result.rate_source}
                {result.transaction_id ? ` | Tx: ${result.transaction_id}` : ""}
              </p>

              <div className="mt-4 space-y-2">
                {/* Base */}
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span className="text-sm text-slate-600">Base de Cálculo (vBC)</span>
                  <span className="font-mono text-sm font-medium text-slate-900">{brlFmt(result.vBC)}</span>
                </div>

                {/* CBS */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-500" />
                    <span className="text-sm text-slate-600">CBS (federal)</span>
                    <span className="text-xs text-slate-400">{pctFmt(result.pCBS)}</span>
                  </div>
                  <span className="font-mono text-sm font-medium text-blue-700">{brlFmt(result.vCBS)}</span>
                </div>

                {/* IBS UF */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" />
                    <span className="text-sm text-slate-600">IBS UF (estadual)</span>
                    <span className="text-xs text-slate-400">{pctFmt(result.pIBSUF)}</span>
                  </div>
                  <span className="font-mono text-sm font-medium text-emerald-700">{brlFmt(result.vIBSUF)}</span>
                </div>

                {/* IBS Mun */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="inline-block h-2.5 w-2.5 rounded-full bg-teal-500" />
                    <span className="text-sm text-slate-600">IBS Mun (municipal)</span>
                    <span className="text-xs text-slate-400">{pctFmt(result.pIBSMun)}</span>
                  </div>
                  <span className="font-mono text-sm font-medium text-teal-700">{brlFmt(result.vIBSMun)}</span>
                </div>

                {/* Divider */}
                <div className="border-t border-slate-200 pt-2" />

                {/* Total */}
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-sm font-semibold text-slate-900">Total Tributos</span>
                    <span className="ml-2 text-xs text-slate-500">
                      Alíquota efetiva: {pctFmt(result.aliquota_efetiva)}
                    </span>
                  </div>
                  <span className="font-mono text-lg font-bold text-slate-900">{brlFmt(result.total_tributos)}</span>
                </div>
              </div>

              {/* Visual bar */}
              {parseFloat(result.total_tributos) > 0 && (
                <div className="mt-4">
                  <div className="flex h-4 overflow-hidden rounded-full">
                    <div
                      className="bg-blue-500"
                      style={{ width: `${(parseFloat(result.vCBS) / parseFloat(result.total_tributos)) * 100}%` }}
                      title={`CBS: ${brlFmt(result.vCBS)}`}
                    />
                    <div
                      className="bg-emerald-500"
                      style={{ width: `${(parseFloat(result.vIBSUF) / parseFloat(result.total_tributos)) * 100}%` }}
                      title={`IBS UF: ${brlFmt(result.vIBSUF)}`}
                    />
                    <div
                      className="bg-teal-400"
                      style={{ width: `${(parseFloat(result.vIBSMun) / parseFloat(result.total_tributos)) * 100}%` }}
                      title={`IBS Mun: ${brlFmt(result.vIBSMun)}`}
                    />
                  </div>
                  <div className="mt-1 flex gap-4 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <span className="inline-block h-2 w-2 rounded-full bg-blue-500" /> CBS
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" /> IBS UF
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="inline-block h-2 w-2 rounded-full bg-teal-400" /> IBS Mun
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* XML Snippet */}
            <div className="rounded-xl border border-slate-200 bg-white">
              <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                <h3 className="text-sm font-semibold text-slate-700">
                  XML &lt;IBSCBS&gt; — pronto para o ERP
                </h3>
                <button
                  type="button"
                  onClick={copyXml}
                  className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  {copied ? "Copiado!" : "Copiar"}
                </button>
              </div>
              <pre className="overflow-x-auto px-4 py-3 font-mono text-xs leading-relaxed text-slate-700">
                {result.xml_snippet}
              </pre>
            </div>

            {/* Share button */}
            <div className="text-center">
              <button
                type="button"
                onClick={copyShareUrl}
                className="text-sm font-medium text-tribultz-600 hover:text-tribultz-700"
              >
                Copiar link para compartilhar
              </button>
            </div>

            {/* Blurred CTA */}
            <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white">
              <div className="pointer-events-none select-none px-4 py-4 blur-sm">
                <p className="text-sm text-slate-600">Simulação de apuração mensal CBS + IBS</p>
                <p className="text-sm text-slate-600">Relatório PDF com memória de cálculo completa</p>
                <p className="text-sm text-slate-600">Histórico de cálculos salvos por CNPJ</p>
              </div>
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 backdrop-blur-[2px]">
                <svg className="h-8 w-8 text-tribultz-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                </svg>
                <p className="mt-2 text-sm font-semibold text-slate-700">{result.upgrade_cta}</p>
                <div className="mt-3 flex gap-3">
                  <Link href="/register" className="rounded-lg bg-tribultz-600 px-5 py-2 text-sm font-semibold text-white hover:bg-tribultz-700">
                    Criar conta gratuita
                  </Link>
                  <Link href="/login" className="rounded-lg border border-slate-300 px-5 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100">
                    Já tenho conta
                  </Link>
                </div>
              </div>
            </div>

            {/* Data governance */}
            <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
              <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
              <div>
                <p className="text-sm font-medium text-emerald-800">Seus dados estão seguros</p>
                <p className="mt-0.5 text-xs text-emerald-700">{result.data_policy}</p>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Info section */}
      <section className="border-t border-slate-200 bg-white px-4 py-10">
        <div className="mx-auto max-w-4xl rounded-xl border border-tribultz-100 bg-tribultz-50 p-5">
          <h3 className="text-base font-semibold text-slate-900">Como funciona a calculadora</h3>
          <p className="mt-2 text-sm text-slate-700">
            A calculadora aplica as alíquotas de referência da LC 214/2025 (Reforma Tributária) para
            CBS (federal) e IBS (estadual + municipal). Para NCMs de alimentos da Cesta Básica Nacional,
            farmacêuticos e educação, aplica automaticamente as reduções previstas nos Anexos da lei.
            O XML gerado segue o leiaute da NT 2025.002-RTC.
          </p>
        </div>
      </section>

      {/* Social proof */}
      <section className="border-t border-slate-200 bg-slate-50 px-4 py-12">
        <div className="mx-auto grid max-w-4xl gap-8 md:grid-cols-3">
          <div className="text-center">
            <p className="text-3xl font-extrabold text-tribultz-600">27</p>
            <p className="mt-1 text-sm text-slate-600">UFs com alíquotas diferenciadas</p>
          </div>
          <div className="text-center">
            <p className="text-3xl font-extrabold text-tribultz-600">14</p>
            <p className="mt-1 text-sm text-slate-600">CSTs da Reforma Tributária</p>
          </div>
          <div className="text-center">
            <p className="text-3xl font-extrabold text-tribultz-600">26.5%</p>
            <p className="mt-1 text-sm text-slate-600">alíquota referência CBS+IBS</p>
          </div>
        </div>
      </section>
    </>
  );
}

export default function CalculadoraPage() {
  return (
    <Suspense>
      <CalculadoraInner />
    </Suspense>
  );
}
