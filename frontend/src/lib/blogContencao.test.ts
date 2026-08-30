/**
 * Guards de contenção editorial e de data do blog (ROUND BLOG 30/08-A).
 *
 * Dois defeitos reais que estes testes travam:
 *
 * 1. **Não existia mecanismo de contenção.** Todo `.mdx` em `content/blog/`
 *    virava página, entrava na listagem e no sitemap. Não havia como tirar do
 *    ar um artigo tecnicamente incorreto sem apagá-lo — e apagar destrói
 *    histórico e cria 404 sem destino avaliado.
 *
 * 2. **O fix de "Invalid Date" (#633) deixou dois pontos para trás.** Ele
 *    cobriu `publishedAt` na listagem, na página e no `<pubDate>` do RSS, mas
 *    `updatedAt` e o `<lastBuildDate>` continuaram no padrão defeituoso
 *    `new Date(x + "T00:00:00")`. O `lastBuildDate` estava quebrado EM
 *    PRODUÇÃO — quebrou quando um post com `publishedAt` ISO virou o mais
 *    recente. Guard de string-fonte é proposital: o defeito é sintático.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { parsePostDate, formatPostDate, formatPostDateRfc822 } from "./formatPostDate";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const src = (p: string) => readFileSync(join(raiz, "src", p), "utf8");
const posts = readdirSync(join(raiz, "content", "blog")).filter((f) => f.endsWith(".mdx"));
const mdx = (f: string) => readFileSync(join(raiz, "content", "blog", f), "utf8");

test("listagem, sitemap e RSS consomem apenas posts indexáveis", () => {
  for (const arq of ["app/blog/page.tsx", "app/sitemap.ts", "app/blog/feed.xml/route.ts"]) {
    const s = src(arq);
    assert.ok(s.includes("getIndexablePosts"), `${arq} deve usar getIndexablePosts`);
    assert.ok(!s.includes("getAllPosts"), `${arq} não pode usar getAllPosts — post contido vazaria`);
  }
});

test("a rota do post contido continua existindo — contenção não é remoção", () => {
  // generateStaticParams usa getAllSlugs (todos), para a URL responder.
  assert.ok(src("app/blog/[slug]/page.tsx").includes("getAllSlugs()"));
});

test("post contido recebe robots noindex", () => {
  const s = src("app/blog/[slug]/page.tsx");
  assert.ok(s.includes("post.noindex"));
  assert.ok(/robots:\s*\{\s*index:\s*false/.test(s));
});

test("nenhuma data do blog usa o padrão defeituoso `+ \"T00:00:00\"`", () => {
  // Era isto que produzia "Invalid Date" com publishedAt/updatedAt em ISO.
  for (const arq of ["app/blog/page.tsx", "app/blog/[slug]/page.tsx", "app/blog/feed.xml/route.ts"]) {
    assert.ok(
      !src(arq).includes('+ "T00:00:00"'),
      `${arq} voltou a concatenar T00:00:00 — reintroduz Invalid Date em data ISO`,
    );
  }
});

test("o parser único sobrevive aos dois formatos e recusa lixo", () => {
  assert.ok(parsePostDate("2026-06-05"));
  assert.ok(parsePostDate("2026-08-29T04:21:32.000Z"));
  assert.equal(parsePostDate("2026-08-29T04:21:32.000ZT00:00:00"), null);
  assert.equal(formatPostDate("lixo"), "");
  assert.equal(formatPostDateRfc822(undefined), "");
  // Nunca estampar "Invalid Date" no leitor.
  for (const v of ["lixo", "", null, undefined, "2026-13-45"]) {
    assert.ok(!formatPostDate(v as string).includes("Invalid"));
    assert.ok(!formatPostDateRfc822(v as string).includes("Invalid"));
  }
});

test("toda data de todo post é parseável", () => {
  for (const f of posts) {
    const s = mdx(f);
    const pub = /^publishedAt:\s*["']?([^"'\n]+?)["']?\s*$/m.exec(s);
    assert.ok(pub, `${f}: publishedAt ausente`);
    assert.ok(parsePostDate(pub![1]), `${f}: publishedAt "${pub![1]}" não parseável`);
    const upd = /^updatedAt:\s*["']?([^"'\n]+?)["']?\s*$/m.exec(s);
    if (upd) assert.ok(parsePostDate(upd[1]), `${f}: updatedAt "${upd[1]}" não parseável`);
  }
});

test("todo post contido declara o motivo da contenção", () => {
  for (const f of posts) {
    const s = mdx(f);
    if (/^noindex:\s*true\s*$/m.test(s)) {
      assert.ok(/^noindexReason:\s*\S/m.test(s), `${f}: noindex sem noindexReason`);
    }
  }
});

test("a Rejeição 960 está contida (auditoria jurídica de 30/08/2026)", () => {
  const s = mdx("rejeicao-960-nf-e.mdx");
  assert.ok(/^noindex:\s*true\s*$/m.test(s), "960 precisa seguir contida até a reescrita canônica");
  assert.ok(/^noindexReason:\s*\S/m.test(s));
  // Conteúdo preservado: o corpo do artigo continua no arquivo.
  assert.ok(s.length > 2000, "o conteúdo do post não pode ter sido apagado");
});
