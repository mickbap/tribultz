import type { Metadata } from "next";
import type { ReactNode } from "react";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { PublicFooter } from "@/components/public/PublicFooter";

export const metadata: Metadata = {
  title: "Diagnóstico Gratuito NF-e — Conformidade IBS/CBS 2026 | Tribultz",
  description:
    "Valide sua NF-e, NFC-e ou NFS-e gratuitamente contra as 14 regras da NT 2025.002-RTC. " +
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
      <PublicNavbar />
      <main className="flex-1">{children}</main>
      <PublicFooter />
    </div>
  );
}
