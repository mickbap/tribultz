import type { Metadata } from "next";
import { JsonLd } from "@/components/seo/JsonLd";
import { PRICING_SCHEMA } from "@/components/seo/schemas";

export const metadata: Metadata = {
  title: "Planos e Preços — Compliance CBS/IBS a partir de R$ 49,90",
  description:
    "Planos para autônomos, PMEs, contadores e empresas com filiais. " +
    "API NCM → cClassTrib, export TOTVS/SAP/Omie/Linx, PDF auditável. " +
    "Penalidades CBS/IBS a partir de agosto/2026.",
  keywords: [
    "preço software CBS IBS", "planos validação fiscal reforma tributária",
    "API cClassTrib preço", "software compliance CBS IBS", "validação NF-e CBS planos",
  ],
  openGraph: {
    title: "Planos Tribultz — Compliance CBS/IBS a partir de R$ 49,90",
    description:
      "API NCM → cClassTrib, export TOTVS/SAP/Omie/Linx e PDF auditável. Penalidades CBS/IBS a partir de agosto/2026.",
    type: "website",
  },
};

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <JsonLd data={PRICING_SCHEMA} />
      {children}
    </>
  );
}
