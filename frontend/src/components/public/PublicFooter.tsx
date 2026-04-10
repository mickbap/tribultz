import Link from "next/link";
import { LEGAL_LINKS } from "@/lib/legal";

export function PublicFooter() {
  return (
    <footer className="border-t border-slate-200 bg-slate-50">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 px-4 py-8 text-sm text-slate-500 md:flex-row md:justify-between">
        <p>&copy; {new Date().getFullYear()} Tribultz. Todos os direitos reservados.</p>
        <nav className="flex gap-4" aria-label="Links do rodapé">
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
    </footer>
  );
}
