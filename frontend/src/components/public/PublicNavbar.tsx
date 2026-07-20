import Link from "next/link";
import { PublicNavbarMobileMenu } from "./PublicNavbarMobileMenu";
import { PUBLIC_NAV_LINKS } from "./publicNavLinks";

function TribultzLogo({ dark = false }: { dark?: boolean }) {
  const textColor = dark ? "#FFFFFF" : "#24292E";
  return (
    <svg viewBox="0 0 200 44" width="160" height="36" aria-label="Tribultz">
      <rect x="2" y="2" width="36" height="36" rx="9" fill="#2956E3" />
      <path d="M11 14 H29 M20 14 V32" stroke="#FFFFFF" strokeWidth="4" strokeLinecap="round" />
      <circle cx="29" cy="32" r="2.5" fill="#FFD600" />
      <text x="46" y="28" fontFamily="Montserrat, sans-serif" fontWeight="800" fontSize="22" letterSpacing="-0.4" fill={textColor}>Tribultz</text>
    </svg>
  );
}

export { TribultzLogo };

export function PublicNavbar() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/92 backdrop-blur-md backdrop-saturate-150">
      <div className="relative mx-auto flex max-w-6xl items-center justify-between px-4 py-3 md:px-6" style={{ height: 64 }}>
        <Link href="/" aria-label="Tribultz">
          <TribultzLogo />
        </Link>

        <nav className="hidden items-center gap-7 text-sm md:flex" aria-label="Navegação pública">
          {PUBLIC_NAV_LINKS.map((link) => (
            <Link key={link.href} href={link.href} className="font-medium text-slate-600 transition-colors hover:text-[#2956E3]">
              {link.label}
            </Link>
          ))}
          <Link href="/login" className="font-medium text-slate-500 transition-colors hover:text-slate-800">
            Entrar
          </Link>
        </nav>

        <div className="flex items-center gap-2">
          <Link
            href="/register"
            className="whitespace-nowrap rounded-lg bg-[#2956E3] px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-[#2044C7] md:px-4 md:text-sm"
            style={{ boxShadow: "0 8px 24px rgba(41,86,227,0.20)" }}
          >
            Criar conta grátis
          </Link>
          <PublicNavbarMobileMenu />
        </div>
      </div>
    </header>
  );
}
