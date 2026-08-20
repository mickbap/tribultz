import type { Metadata } from "next";
import type { ReactNode } from "react";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { PublicFooter } from "@/components/public/PublicFooter";
import { JsonLd } from "@/components/seo/JsonLd";
import { DIAGNOSTICO_SCHEMA } from "@/components/seo/schemas";
import { RULES_COUNT } from "@/lib/validation/rulesMeta";

export const metadata: Metadata = {
  alternates: { canonical: "/diagnostico" },
  title: "Diagnóstico Gratuito NF-e — Conformidade IBS/CBS 2026",
  description:
    `Valide sua NF-e, NFC-e ou NFS-e gratuitamente contra as ${RULES_COUNT} regras da NT 2025.002-RTC. ` +
    "Evite multas de 18% por não destacar IBS e CBS. Diagnóstico instantâneo.",
  openGraph: {
    title: "Diagnóstico Gratuito NF-e — Conformidade IBS/CBS 2026",
    description:
      "80% das empresas ainda não parametrizaram IBS/CBS. Faça o diagnóstico gratuito da sua nota fiscal.",
    type: "website",
  },
};

export default function DiagnosticoLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <JsonLd data={DIAGNOSTICO_SCHEMA} />
      <PublicNavbar />
      <main className="flex-1">{children}</main>
      <PublicFooter />
    </div>
  );
}
