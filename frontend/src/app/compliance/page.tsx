"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/common/Skeleton";
import { Toast } from "@/components/common/Toast";
import { ComplianceHistory, ComplianceScore, getComplianceHistory, getComplianceScore } from "@/lib/api";

function ScoreGauge({ pct }: { pct: number }) {
  const color = pct >= 90 ? "#10b981" : pct >= 70 ? "#f59e0b" : "#ef4444";
  const label = pct >= 90 ? "Excelente" : pct >= 70 ? "Atenção" : "Crítico";
  const radius = 54;
  const circ = 2 * Math.PI * radius;
  const dash = (pct / 100) * circ;

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="#e2e8f0" strokeWidth="12" />
        <circle
          cx="70" cy="70" r={radius}
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeDashoffset={circ / 4}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.6s ease" }}
        />
        <text x="70" y="66" textAnchor="middle" fontSize="22" fontWeight="700" fill={color}>
          {pct.toFixed(1)}%
        </text>
        <text x="70" y="82" textAnchor="middle" fontSize="11" fill="#94a3b8">
          {label}
        </text>
      </svg>
    </div>
  );
}

function HistoryChart({ data }: { data: ComplianceHistory[] }) {
  const sorted = [...data].sort((a, b) => a.period.localeCompare(b.period));
  const max = Math.max(...sorted.map((d) => d.score_pct), 100);

  return (
    <div className="flex items-end gap-2" style={{ height: 140 }}>
      {sorted.map((d) => {
        const barH = Math.max((d.score_pct / max) * 110, 2);
        const color = d.score_pct >= 90 ? "bg-emerald-500" : d.score_pct >= 70 ? "bg-amber-400" : "bg-red-400";
        const [yyyy, mm] = d.period.split("-");
        const label = `${mm}/${yyyy.slice(2)}`;
        return (
          <div key={d.period} className="flex flex-1 flex-col items-center gap-1">
            <div className="flex w-full flex-col items-center" style={{ height: 120 }}>
              <div className="flex-1" />
              <div
                className={`w-full max-w-8 rounded-t ${color}`}
                style={{ height: `${barH}px` }}
                title={`${d.period}: ${d.score_pct}%`}
              />
            </div>
            <span className="text-[9px] text-slate-500 leading-tight">{label}</span>
            <span className="text-[9px] font-semibold text-slate-700">{d.score_pct.toFixed(0)}%</span>
          </div>
        );
      })}
    </div>
  );
}

export default function CompliancePage() {
  const [score, setScore] = useState<ComplianceScore | null>(null);
  const [history, setHistory] = useState<ComplianceHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.allSettled([getComplianceScore(), getComplianceHistory()])
      .then(([scoreRes, histRes]) => {
        if (scoreRes.status === "fulfilled") setScore(scoreRes.value);
        else setError((scoreRes.reason as Error)?.message ?? "Erro ao carregar score");
        if (histRes.status === "fulfilled") setHistory(histRes.value);
      })
      .finally(() => setLoading(false));
  }, []);

  const now = new Date();
  const currentPeriod = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

  const prevScore = history.length >= 2 ? history[1]?.score_pct : null;
  const delta = score && prevScore != null ? score.score_pct - prevScore : null;

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Compliance Score</h1>
        <p className="text-sm text-slate-500">
          Índice de conformidade CBS/IBS — calculado mensalmente com base nas validações do período.
        </p>
      </header>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Gauge card */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 flex flex-col items-center justify-center gap-4">
          {loading ? (
            <Skeleton className="h-36 w-36 rounded-full" />
          ) : (
            <>
              <ScoreGauge pct={score?.score_pct ?? 0} />
              <div className="text-center">
                <p className="text-xs text-slate-500 font-medium">Período: {score?.period ?? currentPeriod}</p>
                {delta !== null && (
                  <p className={`mt-1 text-sm font-semibold ${delta >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                    {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)} pp vs. mês anterior
                  </p>
                )}
              </div>
            </>
          )}
        </div>

        {/* Detail metrics */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-4 lg:col-span-2">
          <h2 className="text-sm font-semibold text-slate-700">Detalhamento do mês atual</h2>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-3/4" />
            </div>
          ) : score ? (
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {[
                { label: "NFs Conformes", value: score.nfs_ok, color: "text-emerald-700" },
                { label: "Total NFs", value: score.nfs_total, color: "text-slate-800" },
                { label: "Erros (findings)", value: score.findings_error, color: "text-red-600" },
                { label: "Avisos", value: score.findings_warning, color: "text-amber-600" },
                { label: "Informativos", value: score.findings_info, color: "text-slate-500" },
                {
                  label: "Crédito em risco",
                  value: score.credit_at_risk.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }),
                  color: score.credit_at_risk > 0 ? "text-red-600" : "text-slate-500",
                },
              ].map((m) => (
                <div key={m.label} className="rounded-lg border border-slate-100 p-3">
                  <dt className="text-xs text-slate-500">{m.label}</dt>
                  <dd className={`mt-1 text-xl font-bold tabular-nums ${m.color}`}>{m.value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm text-slate-500">Sem dados disponíveis para o período.</p>
          )}
        </div>
      </div>

      {/* History chart */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-sm font-semibold text-slate-700">Histórico — últimos 12 meses</h2>
        {loading ? (
          <Skeleton className="h-40 w-full" />
        ) : history.length === 0 ? (
          <p className="text-sm text-slate-500">Sem histórico disponível.</p>
        ) : (
          <>
            <HistoryChart data={history} />
            <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
              <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-emerald-500" /> ≥ 90%</span>
              <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-amber-400" /> 70-89%</span>
              <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-red-400" /> &lt; 70%</span>
            </div>
          </>
        )}
      </div>

      {error && <Toast message={error} tone="error" onClose={() => setError(null)} />}
    </section>
  );
}
