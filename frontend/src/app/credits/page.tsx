"use client";

import { Fragment, useEffect, useState } from "react";
import { Skeleton } from "@/components/common/Skeleton";
import { Toast } from "@/components/common/Toast";
import { downloadCreditCsv, downloadCreditPdf, getCreditBalance, getCreditDocuments } from "@/lib/api";
import type { CreditBalanceResponse, CreditPeriodRow, SplitPaymentDoc } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  pending: "Pendente",
  confirmed: "Confirmado",
  credit_released: "Apropriado",
  failed: "Falhou",
};

const STATUS_CLASS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  confirmed: "bg-emerald-100 text-emerald-700",
  credit_released: "bg-tribultz-100 text-tribultz-700",
  failed: "bg-red-100 text-red-700",
};

function fmtBrl(v: string): string {
  const n = parseFloat(v);
  if (isNaN(n)) return v;
  return `R$ ${n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function totals(rows: CreditPeriodRow[]) {
  const sum = (k: keyof CreditPeriodRow) =>
    rows.reduce((acc, r) => acc + parseFloat(String(r[k] ?? "0") || "0"), 0);
  return {
    generated: sum("generated_total"),
    apropriated: sum("apropriated_total"),
    available: sum("available_total"),
    at_risk: sum("at_risk_total"),
  };
}

function SummaryCard({
  label,
  value,
  hint,
  className,
}: {
  label: string;
  value: string;
  hint?: string;
  className: string;
}) {
  return (
    <article className={`rounded-xl border p-4 ${className}`}>
      <p className="text-xs font-semibold uppercase tracking-wide opacity-70">{label}</p>
      <p className="mt-2 text-2xl font-bold">{value}</p>
      {hint ? <p className="mt-0.5 text-xs opacity-70">{hint}</p> : null}
    </article>
  );
}

export default function CreditsPage() {
  const [period, setPeriod] = useState<"month" | "quarter">("month");
  const [data, setData] = useState<CreditBalanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<"csv" | "pdf" | null>(null);
  const [toast, setToast] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [docsByPeriod, setDocsByPeriod] = useState<Record<string, SplitPaymentDoc[]>>({});
  const [docsLoading, setDocsLoading] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setExpanded(null);
    setDocsByPeriod({});
    getCreditBalance(period, 12)
      .then(setData)
      .catch(() => setToast({ tone: "error", message: "Erro ao carregar saldo de crédito" }))
      .finally(() => setLoading(false));
  }, [period]);

  async function handleExportCsv(): Promise<void> {
    setDownloading("csv");
    try {
      const blob = await downloadCreditCsv(period, 12);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `credito-ibs-cbs-${period}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setToast({ tone: "success", message: "CSV exportado" });
    } catch {
      setToast({ tone: "error", message: "Erro ao exportar CSV" });
    } finally {
      setDownloading(null);
    }
  }

  async function handleExportPdf(): Promise<void> {
    setDownloading("pdf");
    try {
      const { blob, isHtmlFallback } = await downloadCreditPdf(period, 12);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `credito-ibs-cbs-${period}.${isHtmlFallback ? "html" : "pdf"}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setToast({
        tone: "success",
        message: isHtmlFallback ? "Relatório exportado (HTML — gerador de PDF indisponível no servidor)" : "PDF exportado",
      });
    } catch {
      setToast({ tone: "error", message: "Erro ao exportar PDF" });
    } finally {
      setDownloading(null);
    }
  }

  async function toggleExpand(row: CreditPeriodRow): Promise<void> {
    if (expanded === row.period) {
      setExpanded(null);
      return;
    }
    setExpanded(row.period);
    if (docsByPeriod[row.period]) return;
    setDocsLoading(row.period);
    try {
      const docs = await getCreditDocuments(row.period, period);
      setDocsByPeriod((prev) => ({ ...prev, [row.period]: docs }));
    } catch {
      setToast({ tone: "error", message: "Erro ao carregar documentos do período" });
      setExpanded(null);
    } finally {
      setDocsLoading(null);
    }
  }

  const rows = data?.periods ?? [];
  const agg = totals(rows);

  return (
    <section className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Crédito IBS/CBS</h1>
          <p className="text-sm text-slate-500">
            Saldo e fluxo de crédito por período — LC 214 (não-cumulatividade plena). Derivado dos
            documentos rastreados em Split Payment.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void handleExportCsv()}
            disabled={downloading !== null || rows.length === 0}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {downloading === "csv" ? "Exportando…" : "Exportar CSV"}
          </button>
          <button
            type="button"
            onClick={() => void handleExportPdf()}
            disabled={downloading !== null || rows.length === 0}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {downloading === "pdf" ? "Exportando…" : "Exportar PDF (trilha auditável)"}
          </button>
        </div>
      </header>

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <SummaryCard
            label="Gerado"
            value={fmtBrl(agg.generated.toFixed(2))}
            hint="Confirmado + Apropriado"
            className="border-emerald-200 bg-emerald-50 text-emerald-900"
          />
          <SummaryCard
            label="Apropriado"
            value={fmtBrl(agg.apropriated.toFixed(2))}
            hint="Crédito já utilizado"
            className="border-tribultz-200 bg-tribultz-50 text-tribultz-900"
          />
          <SummaryCard
            label="Disponível"
            value={fmtBrl(agg.available.toFixed(2))}
            hint="Formalizado, não utilizado"
            className="border-amber-200 bg-amber-50 text-amber-900"
          />
          <SummaryCard
            label="Em Risco"
            value={fmtBrl(agg.at_risk.toFixed(2))}
            hint="Falhas no Split Payment"
            className="border-red-200 bg-red-50 text-red-900"
          />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {(["month", "quarter"] as const).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setPeriod(p)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              period === p
                ? "border-tribultz-500 bg-tribultz-600 text-white"
                : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {p === "month" ? "Mensal" : "Trimestral"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">
          Nenhum crédito IBS/CBS rastreado nos últimos 12 meses.
          <br />
          <span className="text-xs text-slate-400">
            Os créditos aparecem aqui quando documentos têm status de Split Payment atribuído.
          </span>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Período
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-700">
                  Gerado
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-tribultz-700">
                  Apropriado
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-amber-700">
                  Disponível
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-red-700">
                  Em Risco
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                  NFs
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Fragment key={r.period}>
                  <tr
                    className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                    onClick={() => void toggleExpand(r)}
                  >
                    <td className="px-4 py-3 font-medium text-slate-800">{r.period}</td>
                    <td className="px-4 py-3 text-right font-mono">
                      {fmtBrl(r.generated_total)}
                      <span className="ml-1 text-xs text-slate-400">({r.generated_count})</span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {fmtBrl(r.apropriated_total)}
                      <span className="ml-1 text-xs text-slate-400">({r.apropriated_count})</span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {fmtBrl(r.available_total)}
                      <span className="ml-1 text-xs text-slate-400">({r.available_count})</span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {fmtBrl(r.at_risk_total)}
                      <span className="ml-1 text-xs text-slate-400">({r.at_risk_count})</span>
                    </td>
                    <td className="px-4 py-3 text-right text-xs font-medium text-tribultz-600">
                      {expanded === r.period ? "Ocultar ▲" : "Ver NFs ▼"}
                    </td>
                  </tr>
                  {expanded === r.period && (
                    <tr className="border-t border-slate-100 bg-slate-50/60">
                      <td colSpan={6} className="px-4 py-3">
                        {docsLoading === r.period ? (
                          <Skeleton className="h-10 w-full" />
                        ) : (docsByPeriod[r.period]?.length ?? 0) === 0 ? (
                          <p className="py-2 text-xs text-slate-400">Nenhum documento rastreado neste período.</p>
                        ) : (
                          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-400">
                                  <th className="px-3 py-2">Documento</th>
                                  <th className="px-3 py-2">Modelo</th>
                                  <th className="px-3 py-2">Status</th>
                                  <th className="px-3 py-2">Data</th>
                                  <th className="px-3 py-2 text-right">Crédito</th>
                                </tr>
                              </thead>
                              <tbody>
                                {docsByPeriod[r.period]?.map((d) => (
                                  <tr key={d.document_id} className="border-t border-slate-100">
                                    <td className="px-3 py-2 text-slate-700">{d.original_filename ?? d.document_id.slice(0, 8)}</td>
                                    <td className="px-3 py-2 text-slate-500">{d.doc_type}</td>
                                    <td className="px-3 py-2">
                                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${STATUS_CLASS[d.split_payment_status] ?? "bg-slate-100 text-slate-600"}`}>
                                        {STATUS_LABEL[d.split_payment_status] ?? d.split_payment_status}
                                      </span>
                                    </td>
                                    <td className="px-3 py-2 text-slate-500">
                                      {d.created_at ? new Date(d.created_at).toLocaleDateString("pt-BR") : "—"}
                                    </td>
                                    <td className="px-3 py-2 text-right font-mono text-slate-700">
                                      {d.credit_value ? fmtBrl(d.credit_value) : "—"}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {toast ? <Toast message={toast.message} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}
