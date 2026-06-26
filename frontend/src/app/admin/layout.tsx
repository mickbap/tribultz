"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { API_BASE } from "@/lib/api";
import { getToken } from "@/lib/storage";

const NAV = [
  { href: "/admin", label: "Visão geral" },
  { href: "/admin/tenants", label: "Tenants" },
  { href: "/admin/users", label: "Usuários" },
  { href: "/admin/usage", label: "Uso & Operações" },
  { href: "/admin/system", label: "Saúde do sistema" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [state, setState] = useState<"checking" | "ok" | "denied">("checking");

  useEffect(() => {
    // Guard server-side (fonte da verdade): /admin/me só responde 200 a superadmin.
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/admin/me`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!alive) return;
        if (res.ok) {
          setState("ok");
        } else {
          setState("denied");
          router.replace("/dashboard");
        }
      } catch {
        if (alive) {
          setState("denied");
          router.replace("/dashboard");
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, [router]);

  if (state !== "ok") {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">
        {state === "checking" ? "Verificando acesso…" : "Acesso restrito. Redirecionando…"}
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-7xl gap-6 px-4 py-6 md:px-6">
      <aside className="hidden w-52 shrink-0 md:block">
        <div className="sticky top-6 space-y-1">
          <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Admin</p>
          {NAV.map((item) => {
            const active = item.href === "/admin" ? pathname === "/admin" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  active ? "bg-[#2956E3] text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </aside>
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
