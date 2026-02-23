"use client";

import { useEffect, useState } from "react";
import { getMockMode, getTenantId, setTenantId } from "@/lib/storage";

type TopbarProps = {
  onOpenMenu: () => void;
  stateVersion: number;
  onTenantChanged: () => void;
};

const tenants = ["tenant-a", "tenant-b", "tenant-prod"];

export function Topbar({ onOpenMenu, stateVersion, onTenantChanged }: TopbarProps) {
  const [tenant, setTenant] = useState("tenant-a");
  const [mockMode, setMock] = useState(true);

  useEffect(() => {
    const refresh = () => {
      setTenant(getTenantId());
      setMock(getMockMode());
    };
    refresh();
    window.addEventListener("tribultz-settings-updated", refresh);
    return () => {
      window.removeEventListener("tribultz-settings-updated", refresh);
    };
  }, [stateVersion]);

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
          <p className="text-sm font-semibold text-slate-700">TRIBULTZ Console v2</p>
          <p className="text-xs text-slate-500">{mockMode ? "Mock Mode" : "API Mode"}</p>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <input
            aria-label="Busca global (placeholder)"
            placeholder="Buscar (em breve)"
            className="hidden rounded-lg border border-slate-300 bg-slate-50 px-3 py-1.5 text-sm md:block"
            disabled
          />
          <label className="flex items-center gap-2 text-sm" htmlFor="tenant-select">
            <span className="text-slate-500">Tenant</span>
            <select
              id="tenant-select"
              value={tenant}
              onChange={(e) => {
                setTenantId(e.target.value);
                setTenant(e.target.value);
                onTenantChanged();
              }}
              className="rounded-md border border-slate-300 bg-white px-2 py-1"
              aria-label="Selecionar tenant"
            >
              {tenants.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <div className="grid h-8 w-8 place-items-center rounded-full bg-tribultz-100 text-xs font-bold text-tribultz-700">
            TB
          </div>
        </div>
      </div>
    </header>
  );
}
