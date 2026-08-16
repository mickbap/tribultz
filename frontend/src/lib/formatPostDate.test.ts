/**
 * #633 — Invalid Date no blog. Cobre os dois formatos que convivem no
 * frontmatter, a entrada inválida, e a armadilha de fuso que o parser precisa
 * evitar. Inclui a reprodução literal do bug antigo.
 */

import test from "node:test";
import assert from "node:assert/strict";

import { formatPostDate, formatPostDateRfc822, parsePostDate } from "./formatPostDate";
import { lintBlogFiscal, type ClassTribValid } from "./blogFiscalLint";

const VAZIO: ClassTribValid = { codes: new Set(["000001"]), csts: new Set(["000"]) };

test("data pura (YYYY-MM-DD) formata no dia correto", () => {
  assert.equal(formatPostDate("2026-06-05"), "05 de junho de 2026");
});

test("data pura NÃO escorrega um dia por causa do fuso", () => {
  // `new Date("2026-06-05")` é meia-noite UTC; formatado em America/Sao_Paulo
  // (UTC−3) viraria 04/06. A âncora em -03:00 é o que impede isso.
  assert.ok(
    !formatPostDate("2026-06-05").startsWith("04"),
    "data pura não pode retroceder um dia na formatação",
  );
});

test("timestamp ISO completo (formato do Soro) formata sem Invalid Date", () => {
  assert.equal(formatPostDate("2026-08-05T05:09:31.000Z"), "05 de agosto de 2026");
});

test("ISO completo é convertido para o fuso de Brasília, não exibido como UTC", () => {
  // 02:00 UTC de 05/08 é 23:00 de 04/08 em São Paulo — o dia exibido deve ser 04.
  assert.equal(formatPostDate("2026-08-05T02:00:00.000Z"), "04 de agosto de 2026");
});

test("entrada não-parseável devolve string vazia, nunca 'Invalid Date'", () => {
  for (const ruim of ["", "   ", "ontem", "2026-13-45", null, undefined]) {
    const saida = formatPostDate(ruim as string);
    assert.equal(saida, "", `${JSON.stringify(ruim)} deveria render vazio`);
    assert.ok(!saida.includes("Invalid"), "nunca estampar Invalid Date na UI");
  }
});

test("reprodução do bug antigo: concatenar T00:00:00 em ISO completo não parseia", () => {
  const doSoro = "2026-08-05T05:09:31.000Z";
  assert.equal(parsePostDate(doSoro + "T00:00:00"), null);
  assert.ok(Number.isNaN(new Date(doSoro + "T00:00:00").getTime()), "era exatamente isto que a UI fazia");
  // E o parser novo resolve o mesmo dado sem a concatenação:
  assert.notEqual(parsePostDate(doSoro), null);
});

test("RSS: pubDate sai em RFC 822 nos dois formatos", () => {
  assert.match(formatPostDateRfc822("2026-06-05"), /^\w{3}, \d{2} \w{3} 2026/);
  assert.match(formatPostDateRfc822("2026-08-05T05:09:31.000Z"), /^\w{3}, \d{2} \w{3} 2026/);
  assert.equal(formatPostDateRfc822("ontem"), "");
});

// ── Gate editorial (regra I do blogFiscalLint) ──────────────────────────────

const post = (frontmatter: string) =>
  `---\ntitle: "x"\ntags: ["a"]\nlegalRefs: [{ instrumento: "LC 214" }]\n${frontmatter}\n---\n\nCorpo.`;

test("lint aceita publishedAt nos dois formatos válidos", () => {
  for (const d of ['publishedAt: "2026-06-05"', 'publishedAt: "2026-08-05T05:09:31.000Z"']) {
    const achados = lintBlogFiscal(post(d), VAZIO).filter((f) => f.rule.startsWith("PUBLISHEDAT"));
    assert.deepEqual(achados, [], `${d} deveria passar`);
  }
});

test("lint erra em publishedAt não-parseável", () => {
  const achados = lintBlogFiscal(post('publishedAt: "ontem"'), VAZIO);
  assert.ok(achados.some((f) => f.rule === "PUBLISHEDAT_INVALIDO" && f.severity === "error"));
});

test("lint erra em publishedAt ausente", () => {
  const achados = lintBlogFiscal(post('description: "sem data"'), VAZIO);
  assert.ok(achados.some((f) => f.rule === "PUBLISHEDAT_AUSENTE" && f.severity === "error"));
});
