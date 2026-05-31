import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "Simulador de Impacto CBS/IBS — Reforma Tributária 2026",
  description:
    "Compare sua carga tributária atual (ICMS + PIS/COFINS + ISS) com o novo regime CBS/IBS. Simule o impacto da Reforma Tributária por regime e setor. Gratuito.",
  keywords: ["simulador reforma tributária", "impacto CBS IBS", "carga tributária 2026", "Lucro Real CBS IBS", "Simples Nacional reforma"],
};

export { SimuladorClient as default } from "./client";
