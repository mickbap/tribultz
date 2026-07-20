"use client";

import Link from "next/link";
import { useState } from "react";
import { PUBLIC_NAV_LINKS } from "./publicNavLinks";

/** Menu hambúrguer do header público — visível só abaixo de md (#502). */
export function PublicNavbarMobileMenu() {
  const [open, setOpen] = useState(false);

  return (
    <div className="md:hidden">
      <button
        type="button"
        aria-label={open ? "Fechar menu de navegação" : "Abrir menu de navegação"}
        aria-expanded={open}
        aria-controls="public-mobile-nav"
        onClick={() => setOpen((v) => !v)}
        className="flex h-10 w-10 items-center justify-center rounded-lg text-slate-700 hover:bg-slate-100"
      >
        {open ? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        ) : (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        )}
      </button>

      {open && (
        <nav
          id="public-mobile-nav"
          aria-label="Navegação pública"
          className="absolute inset-x-0 top-full border-b border-slate-200 bg-white shadow-lg"
        >
          <div className="mx-auto flex max-w-6xl flex-col px-4 py-2">
            {PUBLIC_NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="border-b border-slate-100 py-3 text-sm font-medium text-slate-700 hover:text-[#2956E3]"
              >
                {link.label}
              </Link>
            ))}
            <Link
              href="/login"
              onClick={() => setOpen(false)}
              className="py-3 text-sm font-medium text-slate-500 hover:text-slate-800"
            >
              Entrar
            </Link>
          </div>
        </nav>
      )}
    </div>
  );
}
