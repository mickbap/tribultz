"use client";

import { useState, useCallback } from "react";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { PublicFooter } from "@/components/public/PublicFooter";
import Link from "next/link";
import { API_BASE } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

type Regime = "lucro_real" | "lucro_presumido" | "simples_comercio" | "simples_servicos";
type Setor  = "servicos" | "produtos" | "misto";

type RegimeTaxDetail = { pis_cofins: number; icms: number; iss: number; total: number; aliquota_efetiva_pct: number };
type ReformTaxDetail  = { cbs: number; ibs: number; total: number; aliquota_efetiva_pct: number };
type DeltaDetail      = { valor_absoluto: number; pontos_percentuais: number; variacao_relativa_pct: number; direcao: string };

type SimulatorResult = {
  faturamento_anual: number;
  regime_tributario: string;
  regime_atual: RegimeTaxDetail;
  regime_novo: ReformTaxDetail;
  delta: DeltaDetail;
  insight: string;
  notas: string[];
  disclaimer: string;
};

// ── Constants ─────────────────────────────────────────────────────────────────

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

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v: number, decimals = 2): string {
  return v.toLocaleString("pt-BR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
function fmtR$(v: number): string { return `R$ ${fmt(v)}`; }

function parseFat(raw: string): number {
  const clean = raw.replace(/[^\d,]/g, "").replace(",", ".");
  return parseFloat(clean) || 0;
}

function maskFat(raw: string): string {
  const digits = raw.replace(/\D/g, "");
  if (!digits) return "";
  const n = parseInt(digits, 10);
  return n.toLocaleString("pt-BR");
}

// ── Main component ────────────────────────────────────────────────────────────

export function SimuladorClient() {
  const [faturamento, setFaturamento] = useState("1.000.000");
  const [regime, setRegime]           = useState<Regime>("lucro_presumido");
  const [setor, setSetor]             = useState<Setor>("misto");
  const [pctSvc, setPctSvc]           = useState(50);
  const [result, setResult]           = useState<SimulatorResult | null>(null);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");

  const handleFatChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setFaturamento(maskFat(e.target.value));
  }, []);

  async function handleSimulate() {
    const fat = parseFat(faturamento);
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
      // scroll suave ao resultado
      setTimeout(() => document.getElementById("resultado")?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch {
      setError("Erro ao calcular. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  const up   = result?.delta.direcao === "aumento";
  const down = result?.delta.direcao === "reducao";
  const deltaTextColor = up ? "text-red-600"     : down ? "text-emerald-600" : "text-slate-600";
  const deltaBorder    = up ? "border-red-200"   : down ? "border-emerald-200" : "border-slate-200";
  const deltaBg        = up ? "bg-red-50"         : down ? "bg-emerald-50"     : "bg-slate-50";

  return (
    <>
      <PublicNavbar />

      <main className="min-h-screen bg-[#f8fafc]">
        {/* ── Hero ── */}
        <section
          className="pb-12 pt-14"
          style={{
            background: `radial-gradient(800px 360px at 80% -5%, rgba(41,86,227,0.07), transparent 60%),
                         radial-gradient(600px 280px at 0% 50%, rgba(255,214,0,0.06), transparent 60%)`,
          }}
        >
          <div className="mx-auto max-w-2xl px-4 text-center md:px-6">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full bg-[#FEF2F2] py-1.5 pl-1.5 pr-4">
              <span className="rounded-full bg-[#DC2626] px-2.5 py-1 text-[11px] font-bold uppercase text-white">Urgente</span>
              <span className="text-xs font-semibold text-[#991B1B]">Penalidades CBS/IBS a partir de agosto/2026</span>
            </div>
            <h1 className="text-3xl font-extrabold leading-tight tracking-tight text-[#24292E] md:text-4xl">
              Simule o impacto da Reforma Tributária
            </h1>
            <p className="mt-3 text-base leading-relaxed text-[#475569] md:text-lg">
              Compare a sua carga tributária atual com o novo regime <strong>CBS + IBS</strong>
              {" "}e descubra quanto sua empresa vai pagar a partir de 2026.
            </p>
          </div>
        </section>

        {/* ── Form ── */}
        <section className="mx-auto max-w-2xl px-4 pb-6 md:px-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-7">
            <h2 className="mb-5 text-lg font-bold text-slate-800">Dados da empresa</h2>

            <div className="space-y-4">
              {/* Faturamento */}
              <div>
                <label htmlFor="fat" className="mb-1.5 block text-sm font-semibold text-slate-700">
                  Faturamento anual bruto (R$)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm font-medium text-slate-400">R$</span>
                  <input
                    id="fat"
                    type="text"
                    inputMode="numeric"
                    value={faturamento}
                    onChange={handleFatChange}
                    className="w-full rounded-lg border border-slate-300 py-3 pl-9 pr-3 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder="1.000.000"
                    aria-label="Faturamento anual em reais"
                  />
                </div>
              </div>

              {/* Regime + Setor lado a lado no md */}
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor="regime" className="mb-1.5 block text-sm font-semibold text-slate-700">Regime tributário</label>
                  <select
                    id="regime"
                    value={regime}
                    onChange={(e) => setRegime(e.target.value as Regime)}
                    className="w-full rounded-lg border border-slate-300 bg-white py-3 pl-3 pr-8 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    {REGIMES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                  </select>
                </div>

                <div>
                  <label htmlFor="setor" className="mb-1.5 block text-sm font-semibold text-slate-700">Setor</label>
                  <select
                    id="setor"
                    value={setor}
                    onChange={(e) => setSetor(e.target.value as Setor)}
                    className="w-full rounded-lg border border-slate-300 bg-white py-3 pl-3 pr-8 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    {SETORES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                </div>
              </div>

              {/* Slider % serviços */}
              {setor === "misto" && (
                <div>
                  <label className="mb-2 flex justify-between text-sm font-semibold text-slate-700">
                    <span>Composição da receita</span>
                    <span className="font-mono text-blue-600">{pctSvc}% serviços · {100 - pctSvc}% produtos</span>
                  </label>
                  <input
                    type="range" min={0} max={100} value={pctSvc}
                    onChange={(e) => setPctSvc(Number(e.target.value))}
                    className="h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-blue-600"
                    aria-label={`Percentual de serviços: ${pctSvc}%`}
                  />
                  <div className="mt-1 flex justify-between text-xs text-slate-400">
                    <span>100% produtos</span><span>50/50</span><span>100% serviços</span>
                  </div>
                </div>
              )}
            </div>

            {error && (
              <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </p>
            )}

            <button
              type="button"
              onClick={handleSimulate}
              disabled={loading}
              className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-[#2956E3] py-3.5 text-sm font-bold text-white transition-colors hover:bg-[#2044C7] disabled:cursor-not-allowed disabled:opacity-60"
              style={{ boxShadow: "0 8px 24px rgba(41,86,227,0.25)" }}
            >
              {loading ? (
                <>
                  <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  Calculando...
                </>
              ) : (
                "Simular impacto da Reforma →"
              )}
            </button>
          </div>
        </section>

        {/* ── Resultado ── */}
        {result && (
          <section id="resultado" className="mx-auto max-w-2xl px-4 pb-16 md:px-6">
            <div className="space-y-4">

              {/* Insight */}
              <div className={`rounded-2xl border p-5 ${deltaBg} ${deltaBorder}`}>
                <p className={`text-sm font-semibold leading-relaxed md:text-base ${deltaTextColor}`}>
                  {result.insight}
                </p>
              </div>

              {/* Cards de comparação */}
              <div className="grid gap-3 md:grid-cols-2">

                {/* Regime atual */}
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                  <p className="mb-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">Regime Atual</p>
                  <p className="text-2xl font-extrabold text-slate-900 md:text-3xl">{fmtR$(result.regime_atual.total)}</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Alíquota efetiva: <strong className="text-slate-700">{fmt(result.regime_atual.aliquota_efetiva_pct)}%</strong>
                  </p>
                  <div className="mt-4 space-y-2">
                    {[
                      { label: "PIS/COFINS", v: result.regime_atual.pis_cofins, show: true },
                      { label: "ICMS (~12%)", v: result.regime_atual.icms, show: result.regime_atual.icms > 0 },
                      { label: "ISS (~3%)",  v: result.regime_atual.iss,  show: result.regime_atual.iss  > 0 },
                    ].filter(r => r.show).map(r => (
                      <div key={r.label} className="flex items-center justify-between text-xs text-slate-600">
                        <span>{r.label}</span>
                        <span className="font-mono font-medium">{fmtR$(r.v)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Novo regime */}
                <div className="rounded-2xl border border-blue-200 bg-blue-50 p-5">
                  <p className="mb-1 text-[11px] font-bold uppercase tracking-wider text-blue-400">CBS + IBS (pleno 2033)</p>
                  <p className="text-2xl font-extrabold text-blue-900 md:text-3xl">{fmtR$(result.regime_novo.total)}</p>
                  <p className="mt-0.5 text-xs text-blue-500">
                    Alíquota efetiva: <strong className="text-blue-800">{fmt(result.regime_novo.aliquota_efetiva_pct)}%</strong>
                  </p>
                  <div className="mt-4 space-y-2">
                    {[
                      { label: "CBS (8,80%)",  v: result.regime_novo.cbs },
                      { label: "IBS (17,70%)", v: result.regime_novo.ibs },
                    ].map(r => (
                      <div key={r.label} className="flex items-center justify-between text-xs text-blue-700">
                        <span>{r.label}</span>
                        <span className="font-mono font-medium">{fmtR$(r.v)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Delta */}
              <div className={`flex flex-col gap-1 rounded-2xl border p-5 sm:flex-row sm:items-center sm:justify-between ${deltaBg} ${deltaBorder}`}>
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                    {up ? "Acréscimo" : down ? "Economia" : "Impacto"} anual estimado
                  </p>
                  <p className={`text-2xl font-extrabold md:text-3xl ${deltaTextColor}`}>
                    {up ? "+" : down ? "−" : ""}{fmtR$(result.delta.valor_absoluto)}
                  </p>
                </div>
                <div className="sm:text-right">
                  <p className="text-xs text-slate-500">Variação vs regime atual</p>
                  <p className={`text-xl font-bold ${deltaTextColor}`}>
                    {up ? "+" : down ? "−" : ""}{fmt(result.delta.variacao_relativa_pct)}%
                  </p>
                  <p className={`text-xs ${deltaTextColor}`}>
                    {fmt(result.delta.pontos_percentuais)} p.p. na alíquota efetiva
                  </p>
                </div>
              </div>

              {/* Notas */}
              <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <p className="mb-3 text-sm font-bold text-slate-700">Metodologia</p>
                <ul className="space-y-2">
                  {result.notas.map((n, i) => (
                    <li key={i} className="flex gap-2 text-xs leading-relaxed text-slate-600">
                      <span className="mt-0.5 shrink-0 text-slate-300">•</span>
                      <span>{n}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-4 text-[11px] leading-relaxed text-slate-400">{result.disclaimer}</p>
              </div>

              {/* CTA */}
              <div
                className="rounded-2xl p-6 text-center"
                style={{ background: "linear-gradient(135deg,#2956E3,#1a328b)" }}
              >
                <p className="mb-1 text-base font-extrabold text-white">
                  Sua NF-e está preparada para o novo regime?
                </p>
                <p className="mb-5 text-sm text-white/75">
                  Penalidades CBS/IBS começam em agosto/2026. Valide agora, gratuitamente.
                </p>
                <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
                  <Link
                    href="/register"
                    className="rounded-lg px-6 py-3 text-sm font-bold text-[#24292E] transition-colors hover:brightness-95"
                    style={{ background: "#FFD600" }}
                  >
                    Validar NF-e grátis →
                  </Link>
                  <Link
                    href="/calculadora"
                    className="rounded-lg border border-white/40 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
                  >
                    Calculadora CBS/IBS
                  </Link>
                </div>
              </div>

            </div>
          </section>
        )}
      </main>

      <PublicFooter />
    </>
  );
}
