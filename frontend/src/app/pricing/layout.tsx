import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Planos e Preços",
  description:
    "Conheça os planos Tribultz: Trial, Starter, Profissional, Empresarial e Contador. " +
    "Validação fiscal CBS/IBS a partir de R$49,90/mês.",
  openGraph: {
    title: "Planos e Preços — Tribultz",
    description:
      "Escolha o plano ideal para sua empresa. Validação fiscal CBS/IBS com trilha auditável.",
    type: "website",
  },
};

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
