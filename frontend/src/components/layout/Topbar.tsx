"use client";

import { useEffect, useState } from "react";
import {
  getAccountType,
  getMockMode,
  getTenantId,
  getTenants,
  setTenantId,
  setToken,
  type StoredTenant,
} from "@/lib/storage";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type TopbarProps = {
  onOpenMenu: () => void;
  stateVersion: number;
};

export function Topbar({ onOpenMenu, stateVersion }: TopbarProps) {
  const [tenant, setTenant] = useState("");
  const [tenants, setTenantsState] = useState<StoredTenant[]>([]);
  const [accountType, setAccType] = useState("empresa");
  const [mockMode, setMock] = useState(true);
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    const refresh = () => {
      setTenant(getTenantId());
      setTenantsState(getTenants());
      setAccType(getAccountType());
      setMock(getMockMode());
    };
    refresh();
    window.addEventListener("tribultz-settings-updated", refresh);
    return () => {
      window.removeEventListener("tribultz-settings-updated", refresh);
    };
  }, [stateVersion]);

  const currentTenantName = tenants.find((t) => t.id === tenant)?.name
    ?? tenants.find((t) => t.slug === tenant)?.name
    ?? tenant;

  const isContador = accountType === "contador" && tenants.length > 1;

  async function handleSwitchTenant(tenantId: string) {
    if (mockMode || switching) return;
    const target = tenants.find((t) => t.id === tenantId);
    const targetName = target?.name ?? tenantId;
    if (!window.confirm(`Voce esta mudando para o tenant "${targetName}". Confirma?`)) return;
    setSwitching(true);
    try {
      const token = typeof window !== "undefined"
        ? localStorage.getItem("tribultz.token") ?? ""
        : "";
      const res = await fetch(`${API_BASE}/api/v1/auth/switch-tenant`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          "X-Tenant-Id": tenant,
        },
        body: JSON.stringify({ tenant_id: tenantId }),
      });
      if (res.ok) {
        const data = await res.json();
        setTenantId(tenantId);
        setToken(data.access_token);
        window.dispatchEvent(new Event("tribultz-settings-updated"));
        window.location.reload();
      }
    } finally {
      setSwitching(false);
    }
  }

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="flex items-center gap-3 px-4 py-3 md:px-6">
        <button
          type="button"
          className="rounded border border-slate-300 px-2 py-1 text-sm md:hidden"
          onClick={onOpenMenu}
          aria-label="Abrir menu principal"
        >
          Menu
        </button>

        <div className="hidden md:block">
          <p className="text-sm font-semibold text-slate-700">TRIBULTZ Console</p>
          <p className="text-xs text-slate-500">{mockMode ? "Mock Mode" : "API Mode"}</p>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <input
            aria-label="Busca global (placeholder)"
            placeholder="Buscar (em breve)"
            className="hidden rounded-lg border border-slate-300 bg-slate-50 px-3 py-1.5 text-sm md:block"
            disabled
          />
          <div className="hidden items-center gap-2 text-xs text-slate-500 md:flex">
            {isContador ? (
              <select
                value={tenant}
                onChange={(e) => handleSwitchTenant(e.target.value)}
                disabled={switching}
                className="rounded-md border border-slate-300 bg-white px-2 py-1 font-mono text-xs disabled:opacity-50"
                aria-label="Trocar tenant"
              >
                {tenants.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            ) : (
              <span className="rounded bg-slate-100 px-2 py-0.5 font-mono">{currentTenantName}</span>
            )}
            <span>v0.2.0</span>
          </div>
          <div className="grid h-8 w-8 place-items-center rounded-full bg-tribultz-100 text-xs font-bold text-tribultz-700">
            {accountType === "contador" ? "CT" : "TB"}
          </div>
        </div>
      </div>
    </header>
  );
}
