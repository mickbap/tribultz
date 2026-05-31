"use client";

import { useState } from "react";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { PublicFooter } from "@/components/public/PublicFooter";
import Link from "next/link";
import { API_BASE } from "@/lib/api";

type Regime = "lucro_real" | "lucro_presumido" | "simples_comercio" | "simples_servicos";
type Setor  = "servicos" | "produtos" | "misto";

type RegimeTaxDetail = { pis_cofins: number; icms: number; iss: number; total: number; aliquota_efetiva_pct: number };
type ReformTaxDetail  = { cbs: number; ibs: number; total: number; aliquota_efetiva_pct: number };
type DeltaDetail      = { valor_absoluto: number; pontos_percentuais: number; variacao_relativa_pct: number; direcao: string };

type SimulatorResult = {
  faturamento_anual: number;
  regime_tributario: string;
  setor: string;
  percentual_servicos: number;
  regime_atual: RegimeTaxDetail;
  regime_novo: ReformTaxDetail;
  delta: DeltaDetail;
  insight: string;
  notas: string[];
  disclaimer: string;
};

const REGIMES: { value: Regime; label: string }[] = [
  { value: "lucro_real",       label: "Lucro Real" },
  { value: "lucro_presumido",  label: "Lucro Presumido" },
  { value: "simples_comercio", label: "Simples Nacional — Comércio" },
  { value: "simples_servicos", label: "Simples Nacional — Serviços" },
];

const SETORES: { value: Setor; label: string }[] = [
  { value: "servicos", label: "Serviços" },
  { value: "produtos", label: "Produtos / Comércio" },
  { value: "misto",    label: "Misto (serviços + produtos)" },
];

function fmt(v: number, decimals = 2): string {
  return v.toLocaleString("pt-BR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtCurrency(v: number): string {
  return `R$ ${fmt(v)}`;
}

function parseFaturamento(raw: string): number {
  return parseFloat(raw.replace(/\./g, "").replace(",", ".")) || 0;
}

export default function SimuladorPage() {
  const [faturamento, setFaturamento] = useState("1.000.000");
  const [regime, setRegime]           = useState<Regime>("lucro_presumido");
  const [setor, setSetor]             = useState<Setor>("misto");
  const [pctSvc, setPctSvc]           = useState(50);
  const [result, setResult]           = useState<SimulatorResult | null>(null);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");

  async function handleSimulate() {
    const fat = parseFaturamento(faturamento);
    if (!fat || fat <= 0) { setError("Informe um faturamento válido."); return; }
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/public/simulator/regime`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          faturamento_anual: fat,
          regime_tributario: regime,
          setor,
          percentual_servicos: setor === "servicos" ? 100 : setor === "produtos" ? 0 : pctSvc,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResult(await res.json());
    } catch (e) {
      setError("Erro ao calcular. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  const deltaColor = result?.delta.direcao === "aumento" ? "text-red-600" : "text-emerald-600";
  const deltaBg    = result?.delta.direcao === "aumento" ? "bg-red-50 border-red-200" : "bg-emerald-50 border-emerald-200";

  return (
    <>
      <PublicNavbar />
      <main className="min-h-screen bg-[#f8fafc] py-16">
        <div className="mx-auto max-w-3xl px-4 md:px-6">

          {/* Header */}
          <div className="mb-10 text-center">
            <span className="mb-3 inline-flex items-center gap-2 rounded-full bg-[#FEF2F2] py-1.5 pl-1.5 pr-4">
              <span className="rounded-full bg-[#DC2626] px-2.5 py-1 text-[11px] font-bold uppercase text-white">Novo</span>
              <span className="text-xs font-semibold text-[#991B1B]">Penalidades CBS/IBS a partir de agosto/2026</span>
            </span>
            <h1 className="text-4xl font-extrabold tracking-tight text-[#24292E]">
              Simulador de Impacto da Reforma
            </h1>
            <p className="mt-3 text-lg text-[#334155]">
              Calcule quanto sua empresa vai pagar de <strong>CBS + IBS</strong> no regime pleno
              e compare com a carga tributária atual.
            </p>
          </div>

          {/* Form */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="grid gap-5 md:grid-cols-2">

              <div className="md:col-span-2">
                <label className="mb-1.5 block text-sm font-semibold text-slate-700">
                  Faturamento anual (R$)
                </label>
                <input
                  type="text"
                  value={faturamento}
                  onChange={(e) => setFaturamento(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-blue-500 focus:outline-none"
                  placeholder="Ex: 1.000.000"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-semibold text-slate-700">Regime tributário</label>
                <select
                  value={regime}
                  onChange={(e) => setRegime(e.target.value as Regime)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-blue-500 focus:outline-none"
                >
                  {REGIMES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-semibold text-slate-700">Setor</label>
                <select
                  value={setor}
                  onChange={(e) => setSetor(e.target.value as Setor)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-blue-500 focus:outline-none"
                >
                  {SETORES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>

              {setor === "misto" && (
                <div className="md:col-span-2">
                  <label className="mb-1.5 block text-sm font-semibold text-slate-700">
                    % da receita de serviços: <strong>{pctSvc}%</strong> serviços / <strong>{100 - pctSvc}%</strong> produtos
                  </label>
                  <input
                    type="range" min={0} max={100} value={pctSvc}
                    onChange={(e) => setPctSvc(Number(e.target.value))}
                    className="w-full accent-blue-600"
                  />
                </div>
              )}
            </div>

            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

            <button
              type="button"
              onClick={handleSimulate}
              disabled={loading}
              className="mt-5 w-full rounded-lg bg-[#2956E3] py-3 text-sm font-bold text-white hover:bg-[#2044C7] disabled:opacity-60"
              style={{ boxShadow: "0 8px 24px rgba(41,86,227,0.25)" }}
            >
              {loading ? "Calculando..." : "Simular impacto da Reforma →"}
            </button>
          </div>

          {/* Result */}
          {result && (
            <div className="mt-8 space-y-5">

              {/* Insight */}
              <div className={`rounded-xl border p-5 ${deltaBg}`}>
                <p className={`text-base font-semibold ${deltaColor}`}>{result.insight}</p>
              </div>

              {/* Comparison cards */}
              <div className="grid gap-4 md:grid-cols-2">

                {/* Regime atual */}
                <div className="rounded-xl border border-slate-200 bg-white p-5">
                  <p className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400">Regime Atual</p>
                  <p className="text-3xl font-extrabold text-slate-900">{fmtCurrency(result.regime_atual.total)}</p>
                  <p className="mt-0.5 text-sm text-slate-500">Alíquota efetiva: <strong>{fmt(result.regime_atual.aliquota_efetiva_pct)}%</strong></p>
                  <div className="mt-4 space-y-1.5 text-sm text-slate-600">
                    <div className="flex justify-between">
                      <span>PIS/COFINS</span>
                      <span className="font-mono">{fmtCurrency(result.regime_atual.pis_cofins)}</span>
                    </div>
                    {result.regime_atual.icms > 0 && (
                      <div className="flex justify-between">
                        <span>ICMS (~12%)</span>
                        <span className="font-mono">{fmtCurrency(result.regime_atual.icms)}</span>
                      </div>
                    )}
                    {result.regime_atual.iss > 0 && (
                      <div className="flex justify-between">
                        <span>ISS (~3%)</span>
                        <span className="font-mono">{fmtCurrency(result.regime_atual.iss)}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Reforma */}
                <div className="rounded-xl border border-blue-200 bg-blue-50 p-5">
                  <p className="mb-3 text-xs font-bold uppercase tracking-wider text-blue-400">Reforma (CBS + IBS)</p>
                  <p className="text-3xl font-extrabold text-blue-900">{fmtCurrency(result.regime_novo.total)}</p>
                  <p className="mt-0.5 text-sm text-blue-600">Alíquota efetiva: <strong>{fmt(result.regime_novo.aliquota_efetiva_pct)}%</strong></p>
                  <div className="mt-4 space-y-1.5 text-sm text-blue-700">
                    <div className="flex justify-between">
                      <span>CBS (8,80%)</span>
                      <span className="font-mono">{fmtCurrency(result.regime_novo.cbs)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>IBS (17,70%)</span>
                      <span className="font-mono">{fmtCurrency(result.regime_novo.ibs)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Delta */}
              <div className={`flex items-center justify-between rounded-xl border p-5 ${deltaBg}`}>
                <div>
                  <p className="text-sm font-semibold text-slate-600">
                    {result.delta.direcao === "aumento" ? "Acréscimo" : "Economia"} anual estimado
                  </p>
                  <p className={`text-2xl font-extrabold ${deltaColor}`}>
                    {result.delta.direcao === "aumento" ? "+" : "-"}{fmtCurrency(result.delta.valor_absoluto)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-slate-500">Variação relativa</p>
                  <p className={`text-xl font-bold ${deltaColor}`}>
                    {result.delta.direcao === "aumento" ? "+" : "-"}{fmt(result.delta.variacao_relativa_pct)}%
                  </p>
                </div>
              </div>

              {/* Notas */}
              <div className="rounded-xl border border-slate-200 bg-white p-5">
                <p className="mb-3 text-sm font-semibold text-slate-700">Notas metodológicas</p>
                <ul className="space-y-1.5">
                  {result.notas.map((n, i) => (
                    <li key={i} className="flex gap-2 text-sm text-slate-600">
                      <span className="mt-0.5 text-slate-400">•</span>
                      <span>{n}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-4 text-xs text-slate-400">{result.disclaimer}</p>
              </div>

              {/* CTA */}
              <div className="rounded-xl border border-[#2956E3]/20 bg-[#EEF2FF] p-5 text-center">
                <p className="mb-3 text-sm font-semibold text-[#2044C7]">
                  Valide suas notas fiscais antes que as penalidades comecem em agosto/2026
                </p>
                <div className="flex flex-wrap justify-center gap-3">
                  <Link
                    href="/register"
                    className="rounded-lg bg-[#2956E3] px-5 py-2.5 text-sm font-bold text-white hover:bg-[#2044C7]"
                  >
                    Validar NF-e grátis →
                  </Link>
                  <Link
                    href="/calculadora"
                    className="rounded-lg border border-[#2956E3] px-5 py-2.5 text-sm font-semibold text-[#2956E3] hover:bg-white"
                  >
                    Calculadora CBS/IBS
                  </Link>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
      <PublicFooter />
    </>
  );
}
