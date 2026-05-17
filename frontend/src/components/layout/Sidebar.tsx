"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearSession } from "@/lib/storage";

const links = [
  { href: "/dashboard", label: "Painel" },
  { href: "/compliance", label: "Compliance Score" },
  { href: "/closing", label: "Fechamento" },
  { href: "/validate-xml", label: "Validar XML" },
  { href: "/validate-sped", label: "SPED Fiscal" },
  { href: "/jobs", label: "Jobs" },
  { href: "/audit", label: "Auditoria" },
  { href: "/exceptions", label: "Exceções" },
  { href: "/split-payment", label: "Split Payment" },
  { href: "/billing", label: "Faturamento" },
  { href: "/settings", label: "Configurações" },
  { href: "/support", label: "Suporte" },
];

export function Sidebar({ mobile = false, onNavigate }: { mobile?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();

  function handleLogout(): void {
    clearSession();
    window.dispatchEvent(new Event("tribultz-settings-updated"));
    onNavigate?.();
    router.push("/login");
  }

  return (
    <aside className={`flex flex-col border-r border-slate-200 bg-white ${mobile ? "w-full" : "hidden w-64 md:flex"}`}>
      <div className="border-b border-slate-200 px-4 py-3 flex items-center gap-2.5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg" style={{ background: "#2956E3" }}>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
            <path d="M5 7 H19 M12 7 V19" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
            <circle cx="19" cy="19" r="2" fill="#FFD600" />
          </svg>
        </div>
        <h1 className="text-base font-bold tracking-tight text-[#2956E3]">Tribultz</h1>
      </div>
      <nav className="flex-1 p-3" aria-label="Navegação principal">
        <ul className="space-y-1">
          {links.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={onNavigate}
                  className={`block rounded-lg px-3 py-2 text-sm ${
                    active ? "bg-tribultz-100 text-tribultz-700" : "text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="border-t border-slate-200 p-3 space-y-1">
        <Link
          href="/feedback"
          onClick={onNavigate}
          className={`block rounded-lg px-3 py-2 text-sm ${
            pathname === "/feedback" ? "bg-tribultz-100 text-tribultz-700" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          Feedback
        </Link>
        <Link
          href="/changelog"
          onClick={onNavigate}
          className={`block rounded-lg px-3 py-2 text-sm ${
            pathname === "/changelog" ? "bg-tribultz-100 text-tribultz-700" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          Novidades
        </Link>
        <button
          type="button"
          onClick={handleLogout}
          className="w-full rounded-lg px-3 py-2 text-left text-sm text-slate-500 hover:bg-red-50 hover:text-red-700"
        >
          Sair
        </button>
      </div>
    </aside>
  );
}
