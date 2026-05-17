"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/common/Skeleton";
import { Toast } from "@/components/common/Toast";
import { listSplitPaymentDocs, getSplitPaymentSummary, updateSplitPaymentStatus } from "@/lib/api";
import type { SplitPaymentDoc, SplitPaymentSummary } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  confirmed: "Confirmado",
  credit_released: "Crédito Liberado",
  failed: "Em Risco",
};

const STATUS_CLASSES: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700 border-amber-200",
  confirmed: "bg-emerald-100 text-emerald-700 border-emerald-200",
  credit_released: "bg-tribultz-100 text-tribultz-700 border-tribultz-200",
  failed: "bg-red-100 text-red-700 border-red-200",
};

function fmtBrl(v: string | null | undefined): string {
  if (!v) return "—";
  const n = parseFloat(v);
  return isNaN(n) ? v : `R$ ${n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function SummaryCard({ label, count, total, className }: { label: string; count: number; total: string; className: string }) {
  return (
    <article className={`rounded-xl border p-4 ${className}`}>
      <p className="text-xs font-semibold uppercase tracking-wide opacity-70">{label}</p>
      <p className="mt-2 text-2xl font-bold">{count}</p>
      <p className="mt-0.5 text-sm font-medium">{fmtBrl(total)}</p>
    </article>
  );
}

export default function SplitPaymentPage() {
  const [docs, setDocs] = useState<SplitPaymentDoc[]>([]);
  const [summary, setSummary] = useState<SplitPaymentSummary | null>(null);
  const [filter, setFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  function load(status: string) {
    setLoading(true);
    Promise.allSettled([
      listSplitPaymentDocs(status || undefined),
      getSplitPaymentSummary(),
    ]).then(([docsResult, summaryResult]) => {
      if (docsResult.status === "fulfilled") setDocs(docsResult.value);
      if (summaryResult.status === "fulfilled") setSummary(summaryResult.value);
    }).finally(() => setLoading(false));
  }

  useEffect(() => { load(filter); }, [filter]);

  async function handleStatusChange(doc: SplitPaymentDoc, newStatus: string): Promise<void> {
    setUpdating(doc.document_id);
    try {
      const updated = await updateSplitPaymentStatus(doc.document_id, { status: newStatus });
      setDocs((prev) => prev.map((d) => d.document_id === doc.document_id ? updated : d));
      setToast({ tone: "success", message: `Status atualizado para ${STATUS_LABELS[newStatus] ?? newStatus}` });
      // Refresh summary
      getSplitPaymentSummary().then(setSummary).catch(() => {});
    } catch {
      setToast({ tone: "error", message: "Erro ao atualizar status" });
    } finally {
      setUpdating(null);
    }
  }

  return (
    <section className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Split Payment</h1>
        <p className="text-sm text-slate-500">
          Rastreabilidade de crédito CBS/IBS por NF — LC 214 art. 22. O crédito só é liberado após confirmação do pagamento do imposto.
        </p>
      </header>

      {summary ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <SummaryCard
            label="Pendente"
            count={summary.pending_count}
            total={summary.pending_total}
            className="border-amber-200 bg-amber-50"
          />
          <SummaryCard
            label="Confirmado"
            count={summary.confirmed_count}
            total={summary.confirmed_total}
            className="border-emerald-200 bg-emerald-50"
          />
          <SummaryCard
            label="Crédito Liberado"
            count={summary.credit_released_count}
            total={summary.credit_released_total}
            className="border-tribultz-200 bg-tribultz-50"
          />
          <SummaryCard
            label="Em Risco"
            count={summary.failed_count}
            total={summary.failed_total}
            className="border-red-200 bg-red-50"
          />
        </div>
      ) : loading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24 w-full" />)}
        </div>
      ) : null}

      {summary && summary.at_risk_count > 0 && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <span className="font-semibold">{summary.at_risk_count} NF(s) com crédito em risco</span>
          {" "}— aguardando confirmação há mais de 5 dias.{" "}
          <span className="font-semibold">{fmtBrl(summary.at_risk_total)}</span> em crédito potencialmente perdido.
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {["", "pending", "confirmed", "credit_released", "failed"].map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setFilter(s)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              filter === s
                ? "border-tribultz-500 bg-tribultz-600 text-white"
                : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {s ? STATUS_LABELS[s] : "Todos"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 w-full" />)}
        </div>
      ) : docs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">
          Nenhum documento rastreado no Split Payment ainda.
          <br />
          <span className="text-xs text-slate-400">
            Os documentos aparecem aqui quando o status Split Payment é atribuído via API ou automaticamente pela validação de XML.
          </span>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Documento</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Data</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Status</th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Crédito CBS+IBS</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Ação</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((doc) => {
                const isAtRisk = doc.split_payment_status === "pending" && (doc.days_pending ?? 0) > 5;
                return (
                  <tr key={doc.document_id} className={`border-t border-slate-100 ${isAtRisk ? "bg-red-50" : ""}`}>
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-800 truncate max-w-[200px]">
                        {doc.original_filename ?? doc.doc_type}
                      </p>
                      <p className="text-xs text-slate-400 font-mono">{doc.document_id.slice(0, 8)}…</p>
                      {isAtRisk && (
                        <span className="mt-0.5 inline-block rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-600">
                          {doc.days_pending}d sem confirmação
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-600 text-xs">
                      {new Date(doc.created_at).toLocaleDateString("pt-BR")}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-block rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${STATUS_CLASSES[doc.split_payment_status] ?? ""}`}>
                        {STATUS_LABELS[doc.split_payment_status] ?? doc.split_payment_status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-medium text-slate-700">
                      {fmtBrl(doc.credit_value)}
                    </td>
                    <td className="px-4 py-3">
                      <select
                        disabled={updating === doc.document_id}
                        value={doc.split_payment_status}
                        onChange={(e) => void handleStatusChange(doc, e.target.value)}
                        className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 disabled:opacity-50"
                      >
                        <option value="pending">Pendente</option>
                        <option value="confirmed">Confirmado</option>
                        <option value="credit_released">Crédito Liberado</option>
                        <option value="failed">Em Risco</option>
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {toast ? <Toast message={toast.message} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}
