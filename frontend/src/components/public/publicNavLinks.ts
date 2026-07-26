/** Links do header público — fonte única para o desktop (PublicNavbar) e o menu mobile. */

export type NavLink = { href: string; label: string };
export type NavGroup = { label: string; items: NavLink[] };
export type NavEntry = NavLink | NavGroup;

export function isNavGroup(entry: NavEntry): entry is NavGroup {
  return "items" in entry;
}

/**
 * Agrupado sob "Funcionalidades Gratuitas" para não lotar a barra desktop
 * (7 links soltos deixavam o header apertado) — mesmo conjunto de páginas,
 * navegação em dropdown no lugar de link direto.
 */
export const PUBLIC_NAV_LINKS: NavEntry[] = [
  {
    label: "Funcionalidades Gratuitas",
    items: [
      { href: "/diagnostico", label: "Diagnóstico" },
      { href: "/calculadora", label: "Calculadora CBS/IBS" },
      { href: "/simulador", label: "Simulador de Impacto" },
      { href: "/classificacao", label: "NCM" },
    ],
  },
  { href: "/pricing", label: "Planos" },
  { href: "/founding-partners", label: "Founding Partners" },
  { href: "/blog", label: "Blog" },
];
