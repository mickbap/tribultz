"use client";

import { useAdminData } from "@/lib/useAdminData";

type Tenant = { id: string; name: string; is_active: boolean; users: number; created_at: string };
type Resp = { total: number; items: Tenant[] };

export default function AdminTenantsPage() {
  const { data, error, loading } = useAdminData<Resp>("/api/v1/admin/tenants?limit=100");

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-900">Tenants</h1>
      <p className="mb-5 text-sm text-slate-500">
        {data ? `${data.total} tenant(s)` : "Organizações cadastradas na plataforma."}
      </p>

      {loading && <p className="text-sm text-slate-500">Carregando…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Nome</th>
                <th className="px-4 py-3">Usuários</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Criado em</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{t.name}</td>
                  <td className="px-4 py-3 text-slate-700">{t.users}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${t.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                      {t.is_active ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{new Date(t.created_at).toLocaleDateString("pt-BR")}</td>
                </tr>
              ))}
              {data.items.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-400">Nenhum tenant.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
