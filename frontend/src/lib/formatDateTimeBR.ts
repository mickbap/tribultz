/**
 * Formata data/hora sempre em America/Sao_Paulo ("horário de Brasília"),
 * independente do fuso do navegador ou do runner de testes — #419.
 * Storage (API) permanece UTC; esta função só converte na borda de
 * apresentação (ver knowledge/engineering/tempo-e-auditoria.md no Brain).
 */
const formatter = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "America/Sao_Paulo",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function formatDateTimeBR(input: string | number | Date): string {
  const date = input instanceof Date ? input : new Date(input);
  return formatter.format(date);
}
