import type { Metadata } from "next";
import type { ReactNode } from "react";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { PublicFooter } from "@/components/public/PublicFooter";
import { JsonLd } from "@/components/seo/JsonLd";
import { CLASSIFICACAO_SCHEMA } from "@/components/seo/schemas";

export const metadata: Metadata = {
  alternates: { canonical: "/classificacao" },
  title: "Classificar NCM → cClassTrib CBS/IBS — Evite a Rejeição 1024",
  description:
    "Classifique o NCM e entenda o cClassTrib aplicável na Reforma Tributária (sugestão a validar). " +
    "Evite a Rejeição 1024 em NF-e antes das penalidades CBS/IBS de agosto/2026. " +
    "Ferramenta gratuita — 10 classificações por dia.",
  keywords: [
    "classificar NCM cClassTrib", "NCM CBS IBS", "Rejeição 1024 solução",
    "cClassTrib por NCM", "classificação NCM reforma tributária",
    "NCM para CBS IBS LC 214", "erro cClassTrib NF-e",
  ],
  openGraph: {
    title: "Classificar NCM → cClassTrib | Tribultz",
    description:
      "Evite a Rejeição 1024 — classifique o NCM, entenda o cClassTrib aplicável (a validar) e calcule CBS/IBS antes das penalidades de agosto/2026.",
    type: "website",
  },
};

export default function ClassificacaoLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <JsonLd data={CLASSIFICACAO_SCHEMA} />
      <PublicNavbar />
      <main className="flex-1">{children}</main>
      <PublicFooter />
    </div>
  );
}
