import Link from "next/link";
import { CookiePreferencesLink } from "@/components/common/CookiePreferencesLink";
import { LEGAL_LINKS } from "@/lib/legal";

export function AppLegalFooter() {
  return (
    <footer className="border-t border-slate-200 bg-white px-4 py-4 md:px-6">
      <div className="flex flex-col gap-3 text-xs text-slate-500 md:flex-row md:items-center md:justify-between">
        <p className="max-w-2xl">
          Privacidade, cookies, LGPD e termos se aplicam ao console e às ferramentas
          Tribultz. Dúvidas sobre dados pessoais: <span className="font-medium text-slate-700">dpo@tribultz.com.br</span>.
        </p>
        <nav className="flex flex-wrap gap-3" aria-label="Links legais do console">
          {LEGAL_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="font-medium text-slate-600 hover:text-tribultz-700"
            >
              {link.label}
            </Link>
          ))}
          <CookiePreferencesLink className="font-medium text-slate-600 hover:text-tribultz-700" />
        </nav>
      </div>
    </footer>
  );
}
