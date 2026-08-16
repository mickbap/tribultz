/**
 * Data de publicação de post — parser único, tolerante aos dois formatos (#633).
 *
 * O blog renderizava `new Date(post.publishedAt + "T00:00:00")`. Isso só
 * funciona quando `publishedAt` é data pura (`YYYY-MM-DD`). Os posts vindos do
 * Soro trazem timestamp ISO completo (`2026-08-05T05:09:31.000Z`), e a
 * concatenação produzia `…000ZT00:00:00` → **Invalid Date** na página. Dos 19
 * posts, 15 estavam nesse formato — a maior parte do blog exibia "Invalid Date".
 *
 * O mesmo defeito estava em três lugares: a listagem, a página do post e o
 * `<pubDate>` do RSS (onde "Invalid Date" quebra leitores de feed).
 *
 * Fuso: formatação sempre em America/Sao_Paulo, como manda o padrão de
 * `formatDateTimeBR.ts` (RFC-0030) — storage permanece UTC, a conversão
 * acontece só na borda de apresentação.
 *
 * Data pura é ancorada em `T00:00:00-03:00` de propósito. `new Date("2026-06-05")`
 * é interpretado pelo JS como meia-noite **UTC**; formatado em America/Sao_Paulo
 * (UTC−3, sem horário de verão desde 2019) isso vira 04/06 — um dia a menos. A
 * âncora no offset de Brasília faz o dia do calendário sobreviver à formatação.
 */

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

const longFormatter = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "America/Sao_Paulo",
  day: "2-digit",
  month: "long",
  year: "numeric",
});

/** Converte `publishedAt` em Date, ou `null` se não for parseável. */
export function parsePostDate(input: string | null | undefined): Date | null {
  if (!input) return null;
  const raw = String(input).trim();
  if (!raw) return null;

  // Data pura: ancora no fuso de Brasília para não escorregar um dia.
  const normalized = DATE_ONLY.test(raw) ? `${raw}T00:00:00-03:00` : raw;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * Formata para exibição ("05 de agosto de 2026"). Devolve `""` para entrada
 * não-parseável — a UI não deve estampar "Invalid Date" no rosto do leitor; o
 * gate editorial (`blogFiscalLint`, regra I) é quem barra o post na origem.
 */
export function formatPostDate(input: string | null | undefined): string {
  const date = parsePostDate(input);
  return date ? longFormatter.format(date) : "";
}

/** Formato exigido pelo RSS (RFC 822 via `toUTCString`); `""` se não-parseável. */
export function formatPostDateRfc822(input: string | null | undefined): string {
  const date = parsePostDate(input);
  return date ? date.toUTCString() : "";
}
