"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [stateVersion, setStateVersion] = useState(0);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  if (pathname === "/login") return <>{children}</>;

  return (
    <div className="min-h-screen md:flex">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <Topbar
          stateVersion={stateVersion}
          onOpenMenu={() => setMobileOpen(true)}
          onTenantChanged={() => setStateVersion((v) => v + 1)}
        />
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 bg-slate-900/40 md:hidden" role="dialog" aria-modal="true">
          <div className="h-full w-72 bg-white">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <span className="font-semibold">Menu</span>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="rounded border border-slate-300 px-2 py-1 text-xs"
                aria-label="Fechar menu"
              >
                Fechar
              </button>
            </div>
            <Sidebar mobile onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      ) : null}
    </div>
  );
}
