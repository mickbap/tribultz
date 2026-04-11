"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Toast } from "@/components/common/Toast";
import { getTenantId, getToken } from "@/lib/storage";
import { API_BASE } from "@/lib/api";

export default function SettingsPage() {
  const [tenant, setTenant] = useState("");
  const [tokenDisplay, setTokenDisplay] = useState("");
  const [toast, setToast] = useState<{ tone: "error" | "success" | "info"; msg: string } | null>(null);

  useEffect(() => {
    setTenant(getTenantId());
    setTokenDisplay(getToken() ? "••••••••" : "(não autenticado)");
  }, []);

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Configurações</h1>
        <p className="text-sm text-slate-500">Informações da sessão e seus direitos de dados.</p>
      </header>

      <section className="grid gap-4 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-2">
        <div className="rounded-lg border border-slate-200 px-3 py-2">
          <p className="text-sm font-medium text-slate-800">Ambiente</p>
          <p className="mt-1 break-all text-xs text-slate-500">{API_BASE}</p>
        </div>

        <div className="rounded-lg border border-slate-200 px-3 py-2">
          <p className="text-sm font-medium text-slate-800">Tenant ativo</p>
          <p className="mt-1 text-xs text-slate-500 font-mono">{tenant || "—"}</p>
        </div>

        <div className="rounded-lg border border-slate-200 px-3 py-2">
          <p className="text-sm font-medium text-slate-800">Token de sessão</p>
          <p className="mt-1 text-xs text-slate-500 font-mono">{tokenDisplay}</p>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold text-slate-900">Meus Dados (LGPD)</h2>
        <p className="mt-1 text-sm text-slate-500">
          Seus direitos conforme a Lei Geral de Proteção de Dados (Lei 13.709/2018).
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={async () => {
              const currentToken = getToken();
              const currentTenant = getTenantId();
              try {
                const res = await fetch(`${API_BASE}/api/v1/lgpd/my-data`, {
                  headers: { Authorization: `Bearer ${currentToken}`, "X-Tenant-Id": currentTenant },
                });
                const data = await res.json();
                setToast({ tone: "success", msg: `Dados carregados: ${data.user?.email ?? "OK"}` });
              } catch {
                setToast({ tone: "error", msg: "Falha ao carregar dados." });
              }
            }}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Ver meus dados
          </button>
          <button
            type="button"
            onClick={() => {
              const currentToken = getToken();
              const currentTenant = getTenantId();
              window.open(`${API_BASE}/api/v1/lgpd/export?token=${encodeURIComponent(currentToken)}&tenant=${encodeURIComponent(currentTenant)}`, "_blank");
            }}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Exportar dados (JSON)
          </button>
          <button
            type="button"
            onClick={async () => {
              if (!window.confirm("Tem certeza? Esta ação é irreversível. Seus dados serão anonimizados.")) return;
              const currentToken = getToken();
              const currentTenant = getTenantId();
              try {
                const res = await fetch(`${API_BASE}/api/v1/lgpd/delete-account`, {
                  method: "POST",
                  headers: { Authorization: `Bearer ${currentToken}`, "X-Tenant-Id": currentTenant, "Content-Type": "application/json" },
                });
                if (res.ok) {
                  setToast({ tone: "success", msg: "Conta desativada. Redirecionando..." });
                  setTimeout(() => window.location.href = "/login", 2000);
                } else {
                  const data = await res.json().catch(() => ({}));
                  setToast({ tone: "error", msg: data.detail ?? "Falha ao excluir conta." });
                }
              } catch {
                setToast({ tone: "error", msg: "Falha ao excluir conta." });
              }
            }}
            className="rounded-lg border border-red-300 px-4 py-2 text-sm font-semibold text-red-600 hover:bg-red-50"
          >
            Excluir minha conta
          </button>
        </div>
        <p className="mt-3 text-xs text-slate-400">
          Dados fiscais são retidos conforme obrigação legal. Contato DPO: dpo@tribultz.com.br
        </p>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold text-slate-900">Privacidade e Cookies</h2>
        <p className="mt-1 text-sm text-slate-500">
          O console usa armazenamento local do navegador para sessão e preferências, além de
          controles técnicos de segurança quando necessário.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            href="/privacy"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Política de Privacidade
          </Link>
          <Link
            href="/cookies"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Política de Cookies
          </Link>
          <Link
            href="/terms"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Termos de Uso
          </Link>
        </div>
      </section>

      {toast ? <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}
