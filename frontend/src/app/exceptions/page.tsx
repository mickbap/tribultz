"use client";

import { useEffect, useMemo, useState } from "react";
import { JsonViewer } from "@/components/common/JsonViewer";
import { Skeleton } from "@/components/common/Skeleton";
import { Toast } from "@/components/common/Toast";
import { decideExceptionRequest, listExceptionRequests } from "@/lib/api";
import { ExceptionRequest } from "@/lib/types";

export default function ExceptionsPage() {
  const [rows, setRows] = useState<ExceptionRequest[]>([]);
  const [selected, setSelected] = useState<ExceptionRequest | null>(null);
  const [decisionComment, setDecisionComment] = useState("");
  const [filter, setFilter] = useState<"ALL" | "OPEN" | "APPROVED" | "REJECTED">("OPEN");
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ tone: "success" | "error" | "info"; msg: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reload(): Promise<void> {
    setLoading(true);
    try {
      const data = await listExceptionRequests();
      setRows(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar exceções.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  const filtered = useMemo(
    () => (filter === "ALL" ? rows : rows.filter((r) => r.status === filter)),
    [rows, filter],
  );

  async function decide(status: "APPROVED" | "REJECTED"): Promise<void> {
    if (!selected) return;
    try {
      await decideExceptionRequest(selected.id, {
        status,
        decision_comment: decisionComment.trim() || undefined,
        decided_by: "coordenador.demo",
      });
      setToast({ tone: "success", msg: `Exceção ${status === "APPROVED" ? "aprovada" : "reprovada"} com sucesso.` });
      setSelected(null);
      setDecisionComment("");
      await reload();
    } catch (err) {
      setToast({ tone: "error", msg: err instanceof Error ? err.message : "Falha ao decidir exceção." });
    }
  }

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Fila de exceções</h1>
        <p className="text-sm text-slate-500">Workflow Operador → Coordenador com trilha de auditoria.</p>
      </header>

      <div className="flex flex-wrap gap-2">
        {(["OPEN", "APPROVED", "REJECTED", "ALL"] as const).map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => setFilter(opt)}
            className={`rounded border px-3 py-1.5 text-sm ${filter === opt ? "border-tribultz-600 bg-tribultz-50 text-tribultz-700" : "border-slate-300"}`}
          >
            {opt}
          </button>
        ))}
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhuma exceção encontrada.</p>
        ) : (
          <div className="scroll-thin overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="px-2 py-2">ID</th>
                  <th className="px-2 py-2">Job</th>
                  <th className="px-2 py-2">Finding</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2">Criada em</th>
                  <th className="px-2 py-2">Ação</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id} className="border-b border-slate-100">
                    <td className="px-2 py-2 font-mono text-xs">{item.id}</td>
                    <td className="px-2 py-2 font-mono text-xs">{item.job_id}</td>
                    <td className="px-2 py-2 font-mono text-xs">{item.finding_id}</td>
                    <td className="px-2 py-2">{item.status}</td>
                    <td className="px-2 py-2 text-slate-600">{new Date(item.created_at).toLocaleString()}</td>
                    <td className="px-2 py-2">
                      <button
                        type="button"
                        onClick={() => setSelected(item)}
                        className="text-tribultz-700 hover:underline"
                      >
                        Detalhar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selected ? (
        <div className="fixed inset-0 z-40 bg-slate-900/40" role="dialog" aria-modal="true">
          <div className="mx-auto mt-10 w-[95%] max-w-2xl rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-800">Detalhe da exceção</p>
                <p className="text-xs font-mono text-slate-500">{selected.id}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="rounded border border-slate-300 px-2 py-1 text-xs"
              >
                Fechar
              </button>
            </div>

            <JsonViewer
              title="Payload da exceção"
              data={{
                ...selected,
                retention_requirement: "5 anos (contractual MVP: armazenado e exportável)",
              }}
            />

            {selected.status === "OPEN" ? (
              <div className="mt-3 space-y-2">
                <label className="block text-sm">
                  <span className="mb-1 block text-slate-600">Comentário da decisão</span>
                  <textarea
                    value={decisionComment}
                    onChange={(e) => setDecisionComment(e.target.value)}
                    className="min-h-20 w-full rounded border border-slate-300 p-2 text-sm"
                    placeholder="Registrar base da aprovação/reprovação."
                  />
                </label>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => void decide("REJECTED")}
                    className="rounded border border-red-300 bg-red-50 px-3 py-1.5 text-sm text-red-700"
                  >
                    Reprovar
                  </button>
                  <button
                    type="button"
                    onClick={() => void decide("APPROVED")}
                    className="rounded border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-sm text-emerald-700"
                  >
                    Aprovar
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {error ? <Toast message={error} tone="error" onClose={() => setError(null)} /> : null}
      {toast ? <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}
