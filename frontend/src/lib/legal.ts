export type LegalLink = {
  href: string;
  label: string;
};

export const LEGAL_LINKS: LegalLink[] = [
  { href: "/privacy", label: "Privacidade" },
  { href: "/cookies", label: "Cookies" },
  { href: "/lgpd", label: "LGPD" },
  { href: "/terms", label: "Termos de Uso" },
  { href: "/refund-policy", label: "Reembolso" },
];
