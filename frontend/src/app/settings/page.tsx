"use client";

import { useEffect, useState } from "react";
import { Toast } from "@/components/common/Toast";
import { resetDemoData } from "@/lib/api";
import {
  DEFAULT_TENANT,
  getMockMode,
  getTenantId,
  getToken,
  setMockMode,
  setTenantId,
  setToken,
} from "@/lib/storage";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function SettingsPage() {
  const [mockMode, setMock] = useState(true);
  const [tenant, setTenant] = useState(DEFAULT_TENANT);
  const [token, setTokenValue] = useState("demo-token");
  const [toast, setToast] = useState<{ tone: "error" | "success" | "info"; msg: string } | null>(null);

  useEffect(() => {
    setMock(getMockMode());
    setTenant(getTenantId());
    setTokenValue(getToken());
  }, []);

  function saveSettings(): void {
    setMockMode(mockMode);
    setTenantId(tenant.trim() || DEFAULT_TENANT);
    setToken(token.trim() || "demo-token");
    window.dispatchEvent(new Event("tribultz-settings-updated"));
    setToast({ tone: "success", msg: "Configurações salvas." });
  }

  function reset(): void {
    resetDemoData();
    window.dispatchEvent(new Event("tribultz-settings-updated"));
    setToast({ tone: "info", msg: "Dados de demonstração resetados para o tenant atual." });
  }

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Configurações</h1>
        <p className="text-sm text-slate-500">Controle de Mock Mode, tenant e token para API Mode.</p>
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

        <label className="text-sm">
          <span className="mb-1 block text-slate-500">Tenant</span>
          <select
            value={tenant}
            onChange={(e) => setTenant(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
          >
            <option value="tenant-a">tenant-a</option>
            <option value="tenant-b">tenant-b</option>
            <option value="tenant-prod">tenant-prod</option>
          </select>
        </label>

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

      {toast ? <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}
