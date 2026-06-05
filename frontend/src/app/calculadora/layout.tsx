import type { Metadata } from "next";
import type { ReactNode } from "react";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { PublicFooter } from "@/components/public/PublicFooter";
import { JsonLd } from "@/components/seo/JsonLd";
import { CALCULADORA_SCHEMA } from "@/components/seo/schemas";

export const metadata: Metadata = {
  title: "Calculadora CBS/IBS — Calcule NCM → cClassTrib + Alíquotas LC 214",
  description:
    "Calcule CBS e IBS por NCM e UF gratuitamente. Alíquotas LC 214 atualizadas, " +
    "cClassTrib e base legal incluídos. Evite erros antes das penalidades de agosto/2026.",
  keywords: [
    "calculadora CBS IBS", "calcular IBS CBS NCM", "cClassTrib calculadora",
    "reforma tributária calculadora", "alíquota CBS IBS 2026",
    "calcular CBS IBS por NCM grátis", "calculadora reforma tributária",
  ],
  openGraph: {
    title: "Calculadora CBS/IBS — cClassTrib por NCM | Tribultz",
    description:
      "Calcule CBS e IBS por NCM, UF e CST. Alíquotas LC 214, cClassTrib e base legal. Grátis.",
    type: "website",
  },
};

export default function CalculadoraLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <JsonLd data={CALCULADORA_SCHEMA} />
      <PublicNavbar />
      <main className="flex-1">{children}</main>
      <PublicFooter />
    </div>
  );
}
