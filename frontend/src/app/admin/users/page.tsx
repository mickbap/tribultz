"use client";

import { useState } from "react";
import { useAdminData, adminPost } from "@/lib/useAdminData";

type AdminUser = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
};
type Resp = { total: number; items: AdminUser[] };

export default function AdminUsersPage() {
  const { data, error, loading, reload } = useAdminData<Resp>("/api/v1/admin/users?limit=100");
  const [busy, setBusy] = useState<string | null>(null);

  async function toggleActive(u: AdminUser) {
    const verb = u.is_active ? "suspender" : "reativar";
    if (!window.confirm(`Confirma ${verb} o usuário ${u.email}? A ação fica registrada na auditoria.`)) return;
    setBusy(u.id);
    try {
      await adminPost(`/api/v1/admin/users/${u.id}/active`, { is_active: !u.is_active });
      reload();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Falha na ação.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-900">Usuários</h1>
      <p className="mb-5 text-sm text-slate-500">
        {data ? `${data.total} usuário(s)` : "Usuários cadastrados na plataforma."}
      </p>

      {loading && <p className="text-sm text-slate-500">Carregando…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Nome</th>
                <th className="px-4 py-3">E-mail</th>
                <th className="px-4 py-3">Papel</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Criado em</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{u.full_name}</td>
                  <td className="px-4 py-3 text-slate-700">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${u.role === "superadmin" ? "bg-purple-100 text-purple-700" : "bg-slate-100 text-slate-600"}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${u.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                      {u.is_active ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{new Date(u.created_at).toLocaleDateString("pt-BR")}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => toggleActive(u)}
                      disabled={busy === u.id}
                      className={`rounded-lg px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${u.is_active ? "border border-red-200 text-red-600 hover:bg-red-50" : "border border-green-200 text-green-700 hover:bg-green-50"}`}
                    >
                      {busy === u.id ? "…" : u.is_active ? "Suspender" : "Reativar"}
                    </button>
                  </td>
                </tr>
              ))}
              {data.items.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Nenhum usuário.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
