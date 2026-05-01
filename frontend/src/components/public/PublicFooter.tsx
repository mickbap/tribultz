import Link from "next/link";
import { LEGAL_LINKS } from "@/lib/legal";

export function PublicFooter() {
  return (
    <footer className="border-t border-slate-200 bg-slate-50">
      <div className="mx-auto max-w-6xl px-4 py-8 md:px-6">
        <div className="flex flex-col items-center gap-6 md:flex-row md:justify-between">
          <div className="flex flex-col items-center gap-1 md:items-start">
            <span className="text-base font-bold text-tribultz-600">Tribultz</span>
            <p className="text-xs font-medium text-slate-500">
              IBS e CBS sem erro. Sem multa. Sem susto.
            </p>
            <p className="text-xs text-slate-400">
              &copy; {new Date().getFullYear()} Tribultz — Tecnologia fiscal inteligente
            </p>
          </div>
          <nav className="flex flex-wrap justify-center gap-4 text-sm text-slate-500" aria-label="Links do rodapé">
            {LEGAL_LINKS.map((link) => (
              <Link key={link.href} href={link.href} className="hover:text-slate-700">
                {link.label}
              </Link>
            ))}
            <a href="mailto:contato@tribultz.com.br" className="hover:text-slate-700">
              Contato
            </a>
          </nav>
        </div>
      </div>
    </footer>
  );
}
