"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/dashboard", label: "Painel" },
  { href: "/chat", label: "Chat" },
  { href: "/jobs", label: "Jobs" },
  { href: "/audit", label: "Auditoria" },
  { href: "/settings", label: "Configurações" },
];

export function Sidebar({ mobile = false, onNavigate }: { mobile?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <aside className={`border-r border-slate-200 bg-white ${mobile ? "w-full" : "hidden w-64 md:block"}`}>
      <div className="border-b border-slate-200 px-4 py-4">
        <h1 className="text-base font-bold tracking-wide text-tribultz-700">TRIBULTZ Console</h1>
      </div>
      <nav className="p-3" aria-label="Navegação principal">
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
    </aside>
  );
}
