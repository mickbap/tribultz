"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearSession, setMockMode } from "@/lib/storage";

const links = [
  { href: "/dashboard", label: "Painel" },
  { href: "/closing", label: "Fechamento" },
  { href: "/validate-xml", label: "Validar XML" },
  { href: "/chat", label: "Chat" },
  { href: "/jobs", label: "Jobs" },
  { href: "/audit", label: "Auditoria" },
  { href: "/exceptions", label: "Exceções" },
  { href: "/settings", label: "Configurações" },
];

export function Sidebar({ mobile = false, onNavigate }: { mobile?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();

  function handleLogout(): void {
    clearSession();
    setMockMode(true);
    window.dispatchEvent(new Event("tribultz-settings-updated"));
    onNavigate?.();
    router.push("/login");
  }

  return (
    <aside className={`flex flex-col border-r border-slate-200 bg-white ${mobile ? "w-full" : "hidden w-64 md:flex"}`}>
      <div className="border-b border-slate-200 px-4 py-4">
        <h1 className="text-base font-bold tracking-wide text-tribultz-700">TRIBULTZ Console</h1>
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
      <div className="border-t border-slate-200 p-3">
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
