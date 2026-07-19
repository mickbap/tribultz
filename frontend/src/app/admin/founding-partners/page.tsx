"use client";

import { useState } from "react";
import Link from "next/link";
import { useAdminData, adminPost } from "@/lib/useAdminData";

// Cockpit Operacional do Programa Early Adopters (RFC-0024) — Tela 01. Sobre a
// fundação RFC-0017/ADR-0008: o Grant concede o Plano Contador por uma
// vigência, sem assinatura ASAAS — autorização operacional, nunca cobrança.
export const ORIGINS: { value: string; label: string }[] = [
  { value: "linkedin", label: "LinkedIn" },
  { value: "instagram", label: "Instagram" },
  { value: "indicacao", label: "Indicação" },
  { value: "cliente_6tech", label: "Cliente 6tech" },
  { value: "google", label: "Google" },
  { value: "site", label: "Site" },
  { value: "evento", label: "Evento" },
  { value: "outro", label: "Outro" },
];
export const ORIGIN_LABEL = Object.fromEntries(ORIGINS.map((o) => [o.value, o.label]));
export const RECOGNITION_LABEL: Record<string, string> = {
  early_adopter: "Early Adopter",
  founding_partner: "Founding Partner",
};

type Grant = {
  id: string;
  plan_slug: string;
  starts_at: string;
  ends_at: string;
  status: string;
};
export type EarlyAdopter = {
  id: string;
  empresa: string;
  email: string;
  responsavel: string | null;
  origem: string;
  status: string;
  effective_plan: string | null;
  grant_ends_at: string | null;
  active_grant_id: string | null;
  grants: Grant[];
  proxima_acao: string | null;
  owner_email: string | null;
  recognition: string;
};
type Resp = { total: number; items: EarlyAdopter[] };

function today(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

const EMPTY = {
  empresa: "",
  email: "",
  cnpj: "",
  responsavel: "",
  telefone: "",
  origem: "linkedin",
  initial_password: "",
  starts_on: today(),
  ends_on: today(90),
};

export default function FoundingPartnersPage() {
  const { data, error, loading, reload } = useAdminData<Resp>("/api/v1/admin/founding-partners");
  const [form, setForm] = useState({ ...EMPTY });
  const [busy, setBusy] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy("create");
    setFormError(null);
    try {
      await adminPost("/api/v1/admin/founding-partners", {
        empresa: form.empresa.trim(),
        email: form.email.trim(),
        cnpj: form.cnpj.trim() || null,
        responsavel: form.responsavel.trim() || null,
        telefone: form.telefone.trim() || null,
        origem: form.origem,
        initial_password: form.initial_password,
        grant: { plan_slug: "contador", starts_on: form.starts_on, ends_on: form.ends_on },
      });
      setForm({ ...EMPTY });
      setOpen(false);
      reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Falha ao admitir.");
    } finally {
      setBusy(null);
    }
  }

  async function newGrant(ea: EarlyAdopter) {
    const starts = window.prompt(`Nova concessão para "${ea.empresa}".\nInício (AAAA-MM-DD):`, today());
    if (!starts) return;
    const ends = window.prompt("Término (AAAA-MM-DD):", today(90));
    if (!ends) return;
    setBusy(ea.id);
    try {
      await adminPost(`/api/v1/admin/founding-partners/${ea.id}/grants`, {
        plan_slug: "contador",
        starts_on: starts.trim(),
        ends_on: ends.trim(),
      });
      reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Falha na concessão.");
    } finally {
      setBusy(null);
    }
  }

  async function revoke(ea: EarlyAdopter) {
    if (!ea.active_grant_id) return;
    if (!window.confirm(`Revogar a concessão ativa de "${ea.empresa}"? O acesso reverte imediatamente.`)) return;
    setBusy(ea.id);
    try {
      await adminPost(`/api/v1/admin/founding-partners/grants/${ea.active_grant_id}/revoke`, {});
      reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Falha ao revogar.");
    } finally {
      setBusy(null);
    }
  }

  async function close(ea: EarlyAdopter) {
    if (!window.confirm(`Encerrar o programa para "${ea.empresa}"? Revoga concessões ativas e preserva o histórico.`)) return;
    setBusy(ea.id);
    try {
      await adminPost(`/api/v1/admin/founding-partners/${ea.id}/close`, {});
      reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Falha ao encerrar.");
    } finally {
      setBusy(null);
    }
  }

  const inputCls = "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm";

  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900">Founding Partners</h1>
        <button
          onClick={() => setOpen((v) => !v)}
          className="rounded-lg bg-[#2956E3] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          {open ? "Fechar" : "Admitir empresa"}
        </button>
      </div>
      <p className="mb-5 text-sm text-slate-500">
        Programa Early Adopters. A concessão (Grant) libera o Plano Contador por uma vigência,
        sem assinatura ASAAS — autorização operacional, nunca cobrança.
      </p>

      {open && (
        <form onSubmit={create} className="mb-8 grid grid-cols-1 gap-3 rounded-xl border border-slate-200 p-4 md:grid-cols-2">
          <h2 className="md:col-span-2 text-sm font-semibold text-slate-700">Admitir empresa + conceder acesso</h2>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">Empresa *</label>
            <input className={inputCls} required value={form.empresa} onChange={(e) => setForm({ ...form, empresa: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">E-mail do responsável *</label>
            <input className={inputCls} type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">Responsável</label>
            <input className={inputCls} value={form.responsavel} onChange={(e) => setForm({ ...form, responsavel: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">CNPJ</label>
            <input className={inputCls} value={form.cnpj} onChange={(e) => setForm({ ...form, cnpj: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">Telefone</label>
            <input className={inputCls} value={form.telefone} onChange={(e) => setForm({ ...form, telefone: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">Origem</label>
            <select className={inputCls} value={form.origem} onChange={(e) => setForm({ ...form, origem: e.target.value })}>
              {ORIGINS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">Senha inicial (1º acesso) *</label>
            <input className={inputCls} type="text" required minLength={8} value={form.initial_password} onChange={(e) => setForm({ ...form, initial_password: e.target.value })} placeholder="mín. 8 caracteres" />
          </div>
          <div className="grid grid-cols-2 gap-2 md:col-span-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-500">Vigência — início</label>
              <input className={inputCls} type="date" value={form.starts_on} onChange={(e) => setForm({ ...form, starts_on: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-500">Vigência — término</label>
              <input className={inputCls} type="date" value={form.ends_on} onChange={(e) => setForm({ ...form, ends_on: e.target.value })} />
            </div>
          </div>
          {formError && <p className="md:col-span-2 text-sm text-red-600">{formError}</p>}
          <div className="md:col-span-2">
            <button type="submit" disabled={busy === "create"} className="rounded-lg bg-[#2956E3] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
              {busy === "create" ? "Admitindo…" : "Admitir e conceder Plano Contador"}
            </button>
          </div>
        </form>
      )}

      {loading && <p className="text-sm text-slate-500">Carregando…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Empresa</th>
                <th className="px-4 py-3">Responsável</th>
                <th className="px-4 py-3">Origem</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Próxima ação</th>
                <th className="px-4 py-3">Owner</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((ea) => (
                <tr key={ea.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">
                    <Link href={`/admin/founding-partners/${ea.id}`} className="hover:underline">{ea.empresa}</Link>
                    <div className="text-xs text-slate-400">{ea.email}</div>
                    {ea.recognition === "founding_partner" && (
                      <span className="mt-1 inline-block rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700">Founding Partner</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{ea.responsavel ?? "—"}</td>
                  <td className="px-4 py-3 text-slate-600">{ORIGIN_LABEL[ea.origem] ?? ea.origem}</td>
                  <td className="px-4 py-3">
                    <div className={`mb-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${ea.status === "active" ? "bg-green-100 text-green-700" : "bg-slate-200 text-slate-600"}`}>
                      {ea.status === "active" ? "Ativo" : "Encerrado"}
                    </div>
                    <div>
                      {ea.effective_plan ? (
                        <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                          {ea.effective_plan} · até {new Date(ea.grant_ends_at as string).toLocaleDateString("pt-BR")}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-300">sem concessão ativa</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{ea.proxima_acao ?? <span className="text-slate-300">—</span>}</td>
                  <td className="px-4 py-3 text-slate-600">{ea.owner_email ?? <span className="text-slate-300">—</span>}</td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    <Link href={`/admin/founding-partners/${ea.id}`} className="mr-2 rounded-lg border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50">
                      Ver perfil
                    </Link>
                    {ea.status === "active" && (
                      <>
                        {ea.active_grant_id ? (
                          <button onClick={() => revoke(ea)} disabled={busy === ea.id} className="mr-2 rounded-lg border border-amber-200 px-3 py-1 text-xs font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-50">
                            Revogar
                          </button>
                        ) : (
                          <button onClick={() => newGrant(ea)} disabled={busy === ea.id} className="mr-2 rounded-lg border border-blue-200 px-3 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50">
                            Conceder
                          </button>
                        )}
                        <button onClick={() => close(ea)} disabled={busy === ea.id} className="rounded-lg border border-red-200 px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50">
                          Encerrar
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {data.items.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Nenhum Founding Partner ainda.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
