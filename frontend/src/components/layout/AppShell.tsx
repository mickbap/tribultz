"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AppLegalFooter } from "./AppLegalFooter";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import TrialBanner from "@/components/common/TrialBanner";
import { getToken } from "@/lib/storage";

const PUBLIC_ROUTES = [
  "/",
  "/calculadora",
  "/changelog",
  "/cookies",
  "/diagnostico",
  "/forgot-password",
  "/lgpd",
  "/login",
  "/pricing",
  "/privacy",
  "/register",
  "/reset-password",
  "/select-mode",
  "/simulador",
  "/terms",
  "/verify-email",
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [stateVersion, setStateVersion] = useState(0);
  const [authChecked, setAuthChecked] = useState(false);

  const isPublic = useMemo(() => PUBLIC_ROUTES.includes(pathname), [pathname]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Auth guard: redirect to /login if no JWT token on protected routes
  useEffect(() => {
    if (isPublic) {
      setAuthChecked(true);
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
    } else {
      setAuthChecked(true);
    }
  }, [pathname, router, isPublic]);

  // Public routes: render without shell
  if (isPublic) return <>{children}</>;

  // Protected route loading while checking auth
  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-tribultz-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen md:flex">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <TrialBanner />
        <Topbar
          stateVersion={stateVersion}
          onOpenMenu={() => setMobileOpen(true)}
        />
        <main className="flex-1 p-4 md:p-6">{children}</main>
        <AppLegalFooter />
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
