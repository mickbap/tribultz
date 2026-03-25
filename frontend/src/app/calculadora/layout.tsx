import type { Metadata } from "next";
import type { ReactNode } from "react";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { PublicFooter } from "@/components/public/PublicFooter";

export const metadata: Metadata = {
  title: "Calculadora CBS/IBS — Reforma Tributária 2026 | Tribultz",
  description:
    "Calcule CBS e IBS gratuitamente. Insira NCM, UF e valor base para obter " +
    "alíquotas, valores e XML <IBSCBS> pronto para o ERP. LC 214/2025.",
  openGraph: {
    title: "Calculadora CBS/IBS — Reforma Tributária 2026",
    description:
      "Calcule CBS e IBS de qualquer operação. Gere o XML IBSCBS conforme NT 2025.002-RTC.",
    type: "website",
  },
};

export default function CalculadoraLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <PublicNavbar />
      <main className="flex-1">{children}</main>
      <PublicFooter />
    </div>
  );
}
