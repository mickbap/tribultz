"use client";

import { Fragment, useState } from "react";
import { useAdminData, adminPost, adminRequest } from "@/lib/useAdminData";

// Proveniência comercial (RFC-0025). Partner = origem, NUNCA comissão/contrato/financeiro.
const TYPES: { value: string; label: string }[] = [
  { value: "lawyer", label: "Advogado" },
  { value: "accountant", label: "Contador" },
  { value: "consultancy", label: "Consultoria" },
  { value: "erp", label: "ERP" },
  { value: "association", label: "Associação" },
  { value: "influencer", label: "Influenciador" },
  { value: "other", label: "Outro" },
];
const TYPE_LABEL = Object.fromEntries(TYPES.map((t) => [t.value, t.label]));

type Partner = {
  id: string;
  type: string;
  name: string;
  company: string | null;
  email: string | null;
  phone: string | null;
  code: string;
  status: string;
  notes: string | null;
  companies: number;
  has_account: boolean;
  created_at: string;
};
type Resp = { total: number; items: Partner[] };

type ReferredTenant = {
  id: string;
  name: string;
  is_active: boolean;
  users: number;
  created_at: string;
};
type TenantsResp = { total: number; items: ReferredTenant[] };

const EMPTY = { type: "other", name: "", company: "", email: "", phone: "", code: "", notes: "" };

export default function AdminPartnersPage() {
  const { data, error, loading, reload } = useAdminData<Resp>("/api/v1/admin/partners?limit=200");
  const [form, setForm] = useState({ ...EMPTY });
  const [editing, setEditing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [referredByPartner, setReferredByPartner] = useState<Record<string, ReferredTenant[]>>({});
  const [referredLoading, setReferredLoading] = useState<string | null>(null);

  async function toggleExpand(p: Partner): Promise<void> {
    if (expanded === p.id) {
      setExpanded(null);
      return;
    }
    setExpanded(p.id);
    if (referredByPartner[p.id]) return;
    setReferredLoading(p.id);
    try {
      const resp = await adminRequest<TenantsResp>("GET", `/api/v1/admin/tenants?partner_id=${p.id}&limit=200`);
      setReferredByPartner((prev) => ({ ...prev, [p.id]: resp.items }));
    } catch {
      window.alert("Falha ao carregar empresas indicadas.");
      setExpanded(null);
    } finally {
      setReferredLoading(null);
    }
  }

  function edit(p: Partner) {
    setEditing(p.id);
    setForm({
      type: p.type,
      name: p.name,
      company: p.company ?? "",
      email: p.email ?? "",
      phone: p.phone ?? "",
      code: p.code,
      notes: p.notes ?? "",
    });
    setFormError(null);
  }

  function resetForm() {
    setEditing(null);
    setForm({ ...EMPTY });
    setFormError(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      const payload = {
        type: form.type,
        name: form.name.trim(),
        company: form.company.trim() || null,
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        code: form.code.trim().toUpperCase(),
        notes: form.notes.trim() || null,
      };
      if (editing) {
        await adminRequest("PATCH", `/api/v1/admin/partners/${editing}`, payload);
      } else {
        await adminPost("/api/v1/admin/partners", payload);
      }
      resetForm();
      reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Falha ao salvar.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(p: Partner) {
    const verb = p.status === "active" ? "desativar" : "reativar";
    if (!window.confirm(`Confirma ${verb} o Partner "${p.name}"? Fica registrado na auditoria.`)) return;
    setBusy(true);
    try {
      await adminPost(`/api/v1/admin/partners/${p.id}/active`, { is_active: p.status !== "active" });
      reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Falha na ação.");
    } finally {
      setBusy(false);
    }
  }

  // Cadastro operacional do parceiro (RFC-0026, ADR-0011). Sem convite/OTP —
  // o admin define a senha inicial (mesmo padrão do Founding Partner).
  async function createAccount(p: Partner) {
    const email = window.prompt(`Criar conta para "${p.name}".\nE-mail:`, p.email ?? "");
    if (!email) return;
    const initialPassword = window.prompt("Senha inicial (mínimo 8 caracteres):");
    if (!initialPassword) return;
    setBusy(true);
    try {
      await adminPost(`/api/v1/admin/partners/${p.id}/account`, {
        email: email.trim(),
        full_name: p.name,
        initial_password: initialPassword,
      });
      window.alert(`Conta criada para ${email.trim()}. Informe a senha inicial ao parceiro por um canal seguro.`);
      reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Falha ao criar conta.");
    } finally {
      setBusy(false);
    }
  }

  const inputCls = "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm";

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-900">Parceiros</h1>
      <p className="mb-5 text-sm text-slate-500">
        Proveniência comercial — quem apresentou cada empresa à Tribultz. É apenas origem;
        não representa comissão, contrato nem financeiro.
      </p>

      <form onSubmit={submit} className="mb-8 grid grid-cols-1 gap-3 rounded-xl border border-slate-200 p-4 md:grid-cols-2">
        <h2 className="md:col-span-2 text-sm font-semibold text-slate-700">
          {editing ? "Editar Partner" : "Novo Partner"}
        </h2>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">Nome *</label>
          <input className={inputCls} value={form.name} required onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">Código *</label>
          <input
            className={`${inputCls} uppercase`}
            value={form.code}
            required
            placeholder="KATIA"
            onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">Tipo</label>
          <select className={inputCls} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            {TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">Empresa</label>
          <input className={inputCls} value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">E-mail</label>
          <input className={inputCls} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">Telefone</label>
          <input className={inputCls} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        </div>
        <div className="md:col-span-2">
          <label className="mb-1 block text-xs font-medium text-slate-500">Observações</label>
          <textarea className={inputCls} rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
        {formError && <p className="md:col-span-2 text-sm text-red-600">{formError}</p>}
        <div className="md:col-span-2 flex gap-2">
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-[#2956E3] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Salvando…" : editing ? "Salvar alterações" : "Cadastrar Partner"}
          </button>
          {editing && (
            <button type="button" onClick={resetForm} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">
              Cancelar
            </button>
          )}
        </div>
      </form>

      {loading && <p className="text-sm text-slate-500">Carregando…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Código</th>
                <th className="px-4 py-3">Nome</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Empresas</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Conta</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((p) => (
                <Fragment key={p.id}>
                  <tr className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-xs text-slate-700">{p.code}</td>
                    <td className="px-4 py-3 font-medium text-slate-900">{p.name}</td>
                    <td className="px-4 py-3 text-slate-600">{TYPE_LABEL[p.type] ?? p.type}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => void toggleExpand(p)}
                        className="rounded-full border border-slate-200 px-2 py-0.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                        disabled={p.companies === 0}
                      >
                        {p.companies} {expanded === p.id ? "▲" : p.companies > 0 ? "▼" : ""}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${p.status === "active" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                        {p.status === "active" ? "Ativo" : "Inativo"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${p.has_account ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-500"}`}>
                        {p.has_account ? "Criada" : "Sem conta"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => edit(p)} className="mr-2 rounded-lg border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">
                        Editar
                      </button>
                      {!p.has_account && p.status === "active" && (
                        <button
                          onClick={() => createAccount(p)}
                          disabled={busy}
                          className="mr-2 rounded-lg border border-blue-200 px-3 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                        >
                          Criar conta
                        </button>
                      )}
                      <button
                        onClick={() => toggleActive(p)}
                        disabled={busy}
                        className={`rounded-lg px-3 py-1 text-xs font-medium disabled:opacity-50 ${p.status === "active" ? "border border-red-200 text-red-600 hover:bg-red-50" : "border border-green-200 text-green-700 hover:bg-green-50"}`}
                      >
                        {p.status === "active" ? "Desativar" : "Reativar"}
                      </button>
                    </td>
                  </tr>
                  {expanded === p.id && (
                    <tr className="bg-slate-50/60">
                      <td colSpan={7} className="px-4 py-3">
                        {referredLoading === p.id ? (
                          <p className="text-xs text-slate-400">Carregando…</p>
                        ) : (referredByPartner[p.id]?.length ?? 0) === 0 ? (
                          <p className="text-xs text-slate-400">Nenhuma empresa indicada por este Partner ainda.</p>
                        ) : (
                          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-400">
                                  <th className="px-3 py-2">Empresa</th>
                                  <th className="px-3 py-2">Status</th>
                                  <th className="px-3 py-2">Usuários</th>
                                  <th className="px-3 py-2">Cadastrada em</th>
                                </tr>
                              </thead>
                              <tbody>
                                {referredByPartner[p.id]?.map((t) => (
                                  <tr key={t.id} className="border-t border-slate-100">
                                    <td className="px-3 py-2 font-medium text-slate-800">{t.name}</td>
                                    <td className="px-3 py-2">
                                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${t.is_active ? "bg-green-100 text-green-700" : "bg-slate-200 text-slate-600"}`}>
                                        {t.is_active ? "Ativa" : "Inativa"}
                                      </span>
                                    </td>
                                    <td className="px-3 py-2 text-slate-600">{t.users}</td>
                                    <td className="px-3 py-2 text-slate-500">{new Date(t.created_at).toLocaleDateString("pt-BR")}</td>
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
              {data.items.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Nenhum Partner cadastrado.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
