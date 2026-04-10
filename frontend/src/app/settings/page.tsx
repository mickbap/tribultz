"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Toast } from "@/components/common/Toast";
import { resetDemoData } from "@/lib/api";
import {
  getMockMode,
  getTenantId,
  getToken,
  setMockMode,
  setToken,
} from "@/lib/storage";
import { API_BASE } from "@/lib/api";

export default function SettingsPage() {
  const [mockMode, setMock] = useState(true);
  const [tenant, setTenant] = useState("");
  const [token, setTokenValue] = useState("demo-token");
  const [toast, setToast] = useState<{ tone: "error" | "success" | "info"; msg: string } | null>(null);

  useEffect(() => {
    setMock(getMockMode());
    setTenant(getTenantId());
    setTokenValue(getToken());
  }, []);

  function saveSettings(): void {
    setMockMode(mockMode);
    setToken(token.trim() || "demo-token");
    window.dispatchEvent(new Event("tribultz-settings-updated"));
    setToast({ tone: "success", msg: "Configurações salvas." });
  }

  function reset(): void {
    resetDemoData();
    window.dispatchEvent(new Event("tribultz-settings-updated"));
    setToast({ tone: "info", msg: "Dados de demonstração resetados." });
  }

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Configurações</h1>
        <p className="text-sm text-slate-500">Controle de Mock Mode e token para API Mode.</p>
      </header>

      <section className="grid gap-4 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-2">
        <label className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2">
          <span>
            <span className="block text-sm font-medium text-slate-800">Mock Mode (padrão ON)</span>
            <span className="text-xs text-slate-500">Quando ON, o app roda sem backend.</span>
          </span>
          <input
            type="checkbox"
            checked={mockMode}
            onChange={(e) => setMock(e.target.checked)}
            aria-label="Alternar mock mode"
            className="h-4 w-4"
          />
        </label>

        <div className="rounded-lg border border-slate-200 px-3 py-2">
          <p className="text-sm font-medium text-slate-800">Base URL (modo API)</p>
          <p className="mt-1 break-all text-xs text-slate-500">{API_BASE}</p>
        </div>

        <div className="rounded-lg border border-slate-200 px-3 py-2">
          <p className="text-sm font-medium text-slate-800">Tenant</p>
          <p className="mt-1 text-xs text-slate-500 font-mono">{tenant}</p>
          <p className="mt-1 text-xs text-slate-400">Definido pelo perfil do usuário (AWS).</p>
        </div>

        <label className="text-sm">
          <span className="mb-1 block text-slate-500">Token de autorização</span>
          <input
            value={token}
            onChange={(e) => setTokenValue(e.target.value)}
            placeholder="Bearer token"
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </label>
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={saveSettings}
          className="rounded-lg bg-tribultz-600 px-4 py-2 text-sm font-semibold text-white hover:bg-tribultz-700"
        >
          Salvar
        </button>
        <button
          type="button"
          onClick={reset}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
        >
          Resetar demo
        </button>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold text-slate-900">Meus Dados (LGPD)</h2>
        <p className="mt-1 text-sm text-slate-500">
          Seus direitos conforme a Lei Geral de Proteção de Dados (Lei 13.709/2018).
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={async () => {
              if (mockMode) {
                setToast({ tone: "info", msg: "Disponível apenas em API Mode." });
                return;
              }
              try {
                const res = await fetch(`${API_BASE}/api/v1/lgpd/my-data`, {
                  headers: { Authorization: `Bearer ${token}`, "X-Tenant-Id": tenant },
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
            onClick={async () => {
              if (mockMode) {
                setToast({ tone: "info", msg: "Disponível apenas em API Mode." });
                return;
              }
              window.open(`${API_BASE}/api/v1/lgpd/export`, "_blank");
            }}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Exportar dados (JSON)
          </button>
          <button
            type="button"
            onClick={async () => {
              if (mockMode) {
                setToast({ tone: "info", msg: "Disponível apenas em API Mode." });
                return;
              }
              if (!window.confirm("Tem certeza? Esta ação é irreversível. Seus dados serão anonimizados.")) return;
              try {
                const res = await fetch(`${API_BASE}/api/v1/lgpd/delete-account`, {
                  method: "POST",
                  headers: { Authorization: `Bearer ${token}`, "X-Tenant-Id": tenant, "Content-Type": "application/json" },
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
