import Link from "next/link";
import { TribultzLogo } from "./PublicNavbar";
import { CookiePreferencesLink } from "@/components/common/CookiePreferencesLink";
import { LEGAL_LINKS } from "@/lib/legal";

export function PublicFooter() {
  return (
    <footer style={{ background: "#0F1729", color: "#CBD5E1" }}>
      <div className="mx-auto max-w-6xl px-4 py-16 md:px-6">
        <div className="grid gap-12 border-b pb-12 md:grid-cols-4" style={{ borderColor: "#1F2A44" }}>
          {/* Brand col */}
          <div>
            <TribultzLogo dark />
            <p className="mt-5 text-sm leading-relaxed" style={{ color: "#94A3B8", maxWidth: 280 }}>
              Validação CBS/IBS para a Reforma Tributária brasileira. Uma marca{" "}
              <strong className="text-white">6tech</strong>.
            </p>
          </div>

          {/* Produto */}
          <div>
            <h5 className="mb-4 text-xs font-bold uppercase tracking-widest text-white">Produto</h5>
            <ul className="space-y-2.5 text-sm">
              {[
                { href: "/validate-xml", label: "Validador XML" },
                { href: "/validate-sped", label: "SPED Fiscal" },
                { href: "/calculadora", label: "cClassTrib" },
                { href: "/compliance", label: "Compliance Score" },
              ].map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="transition-colors hover:text-white">
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Empresa */}
          <div>
            <h5 className="mb-4 text-xs font-bold uppercase tracking-widest text-white">Empresa</h5>
            <ul className="space-y-2.5 text-sm">
              {[
                { href: "/pricing", label: "Preços" },
                { href: "/changelog", label: "Novidades" },
                { href: "mailto:contato@tribultz.com.br", label: "Contato" },
                { href: "https://wa.me/5551991881026?text=Ol%C3%A1!%20Vim%20pelo%20site%20da%20Tribultz%20e%20quero%20saber%20mais%20sobre%20valida%C3%A7%C3%A3o%20CBS%2FIBS.", label: "💬 WhatsApp (51) 99188-1026", external: true },
              ].map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="transition-colors hover:text-white" {...(l.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Recursos */}
          <div>
            <h5 className="mb-4 text-xs font-bold uppercase tracking-widest text-white">Recursos</h5>
            <ul className="space-y-2.5 text-sm">
              {LEGAL_LINKS.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="transition-colors hover:text-white">
                    {l.label}
                  </Link>
                </li>
              ))}
              <li>
                <Link href="/support" className="transition-colors hover:text-white">
                  Suporte
                </Link>
              </li>
              <li>
                <CookiePreferencesLink className="transition-colors hover:text-white" />
              </li>
            </ul>
          </div>
        </div>

        <div className="flex flex-col items-center justify-between gap-3 pt-6 text-xs md:flex-row" style={{ color: "#64748B" }}>
          <span>© {new Date().getFullYear()} 6tech · Tribultz. Todos os direitos reservados.</span>
          <span>Produzido com Orgulho no Rio Grande do Sul</span>
        </div>
      </div>
    </footer>
  );
}
