"use client";

import { formatDateTimeBR } from "@/lib/formatDateTimeBR";
import { useAdminData } from "@/lib/useAdminData";

type AuditEntry = {
  id: string;
  actor_email: string;
  action: string;
  target_type: string;
  target_id: string | null;
  detail: Record<string, unknown>;
  created_at: string;
};
type Resp = { total: number; items: AuditEntry[] };

const ACTION_LABEL: Record<string, string> = {
  "user.activate": "Reativou usuário",
  "user.deactivate": "Suspendeu usuário",
  "tenant.activate": "Reativou tenant",
  "tenant.deactivate": "Suspendeu tenant",
};

export default function AdminAuditPage() {
  const { data, error, loading } = useAdminData<Resp>("/api/v1/admin/audit-log?limit=100");

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-900">Audit log</h1>
      <p className="mb-5 text-sm text-slate-500">
        Trilha de auditoria de todas as ações administrativas. {data ? `${data.total} registro(s).` : ""}
      </p>

      {loading && <p className="text-sm text-slate-500">Carregando…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Quando</th>
                <th className="px-4 py-3">Quem</th>
                <th className="px-4 py-3">Ação</th>
                <th className="px-4 py-3">Alvo</th>
                <th className="px-4 py-3">Detalhe</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((e) => (
                <tr key={e.id} className="hover:bg-slate-50">
                  <td className="whitespace-nowrap px-4 py-3 text-slate-500">{formatDateTimeBR(e.created_at)}</td>
                  <td className="px-4 py-3 text-slate-700">{e.actor_email}</td>
                  <td className="px-4 py-3 font-medium text-slate-900">{ACTION_LABEL[e.action] ?? e.action}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {String(e.detail.email ?? e.detail.name ?? e.target_id ?? "—")}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    {typeof e.detail.before !== "undefined" ? `${e.detail.before} → ${e.detail.after}` : ""}
                  </td>
                </tr>
              ))}
              {data.items.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Nenhuma ação registrada ainda.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
