"use client";

import { useMemo, useState } from "react";
import { useAdminData, adminPost } from "@/lib/useAdminData";

type Tenant = {
  id: string;
  name: string;
  is_active: boolean;
  users: number;
  created_at: string;
  partner_id: string | null;
  partner_name: string | null;
  partner_code: string | null;
};
type Resp = { total: number; items: Tenant[] };
type Partner = { id: string; name: string; code: string; status: string };
type PartnersResp = { items: Partner[] };

export default function AdminTenantsPage() {
  // Filtro por Partner (proveniência comercial — RFC-0025).
  const [partnerFilter, setPartnerFilter] = useState<string>("");
  const query = `/api/v1/admin/tenants?limit=100${partnerFilter ? `&partner_id=${partnerFilter}` : ""}`;
  const { data, error, loading, reload } = useAdminData<Resp>(query);
  const { data: partners } = useAdminData<PartnersResp>("/api/v1/admin/partners?limit=200");
  const [busy, setBusy] = useState<string | null>(null);

  const partnerOptions = useMemo(() => partners?.items ?? [], [partners]);

  async function toggleActive(t: Tenant) {
    const verb = t.is_active ? "suspender" : "reativar";
    if (!window.confirm(`Confirma ${verb} o tenant "${t.name}"? A ação fica registrada na auditoria.`)) return;
    setBusy(t.id);
    try {
      await adminPost(`/api/v1/admin/tenants/${t.id}/active`, { is_active: !t.is_active });
      reload();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Falha na ação.");
    } finally {
      setBusy(null);
    }
  }

  async function setPartner(t: Tenant) {
    // Atribuição manual da origem (casos vindos do Microsoft Forms — RFC-0025).
    const current = t.partner_id ?? "";
    const options = partnerOptions
      .filter((p) => p.status === "active")
      .map((p) => `${p.code} — ${p.name}`)
      .join("\n");
    const answer = window.prompt(
      `Origem comercial de "${t.name}".\nDigite o CÓDIGO do Partner (ou vazio para desvincular).\n\nPartners ativos:\n${options}`,
      t.partner_code ?? "",
    );
    if (answer === null) return;
    const code = answer.trim().toUpperCase();
    const match = code ? partnerOptions.find((p) => p.code === code) : null;
    if (code && !match) {
      window.alert(`Nenhum Partner com o código ${code}.`);
      return;
    }
    const nextId = match ? match.id : null;
    if ((nextId ?? "") === current) return;
    setBusy(t.id);
    try {
      await adminPost(`/api/v1/admin/tenants/${t.id}/partner`, { partner_id: nextId });
      reload();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Falha na ação.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-900">Tenants</h1>
      <p className="mb-5 text-sm text-slate-500">
        {data ? `${data.total} tenant(s)` : "Organizações cadastradas na plataforma."}
      </p>

      <div className="mb-4 flex items-center gap-2">
        <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Parceiro</label>
        <select
          value={partnerFilter}
          onChange={(e) => setPartnerFilter(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700"
        >
          <option value="">Todos</option>
          {partnerOptions.map((p) => (
            <option key={p.id} value={p.id}>
              {p.code} — {p.name}
            </option>
          ))}
        </select>
      </div>

      {loading && <p className="text-sm text-slate-500">Carregando…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Nome</th>
                <th className="px-4 py-3">Parceiro</th>
                <th className="px-4 py-3">Usuários</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Criado em</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{t.name}</td>
                  <td className="px-4 py-3">
                    {t.partner_name ? (
                      <span title={t.partner_code ?? ""} className="text-slate-700">
                        {t.partner_name}
                      </span>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-700">{t.users}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${t.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                      {t.is_active ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{new Date(t.created_at).toLocaleDateString("pt-BR")}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setPartner(t)}
                      disabled={busy === t.id}
                      className="mr-2 rounded-lg border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50"
                    >
                      Origem
                    </button>
                    <button
                      onClick={() => toggleActive(t)}
                      disabled={busy === t.id}
                      className={`rounded-lg px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${t.is_active ? "border border-red-200 text-red-600 hover:bg-red-50" : "border border-green-200 text-green-700 hover:bg-green-50"}`}
                    >
                      {busy === t.id ? "…" : t.is_active ? "Suspender" : "Reativar"}
                    </button>
                  </td>
                </tr>
              ))}
              {data.items.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Nenhum tenant.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
