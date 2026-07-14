/**
 * Prazo de produção da SEFAZ (Regime Normal/CRT 3, Rejeições 1115/1119 — NT 2025.002
 * v1.40, #403). Usado pelo banner de contagem regressiva no /validate-xml (#407).
 */
export const DEADLINE = new Date("2026-08-03T00:00:00-03:00");

export function daysUntilDeadline(now: Date = new Date()): number {
  const diffMs = DEADLINE.getTime() - now.getTime();
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
}
