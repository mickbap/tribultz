import test from "node:test";
import assert from "node:assert/strict";
import { parseFeedToPosts, postToMdx, slugify } from "./soroSync";

// Item real do feed Soro (estrutura capturada de app.trysoro.com/api/rss/...).
const FEED = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>tribultz.com.br</title>
    <item>
      <title>Como calcular alíquota CBS IBS sem erro</title>
      <link>https://tribultz.com.br/como-calcular-aliquota-cbs-ibs</link>
      <guid>4aa3737a-e38b-4624-a082-2472b7b92a70</guid>
      <pubDate>Thu, 25 Jun 2026 14:13:01 GMT</pubDate>
      <description>Veja como calcular alíquota CBS IBS com base legal.</description>
      <content:encoded><![CDATA[<p>Texto do artigo com <a href="https://x">link</a>.</p>]]></content:encoded>
      <enclosure url="https://cdn.example/img.webp" type="image/webp" />
      <media:content url="https://cdn.example/img.webp" medium="image" />
    </item>
  </channel>
</rss>`;

test("#349 parseFeedToPosts extrai os campos do item Soro", () => {
  const [p] = parseFeedToPosts(FEED);
  assert.equal(p.title, "Como calcular alíquota CBS IBS sem erro");
  assert.equal(p.slug, "como-calcular-aliquota-cbs-ibs"); // derivado do <link>
  assert.equal(p.guid, "4aa3737a-e38b-4624-a082-2472b7b92a70");
  assert.equal(p.coverImage, "https://cdn.example/img.webp");
  assert.equal(p.publishedAt, "2026-06-25T14:13:01.000Z"); // RFC822 → ISO
  assert.ok(p.contentHtml.includes("<p>Texto do artigo"));
  assert.ok(!p.contentHtml.includes("CDATA"));
});

test("#349 postToMdx gera frontmatter válido + corpo, com legalRefs/tags vazios para revisão", () => {
  const [p] = parseFeedToPosts(FEED);
  const { filename, mdx } = postToMdx(p);
  assert.equal(filename, "como-calcular-aliquota-cbs-ibs.mdx");
  assert.ok(mdx.startsWith("---\n"));
  assert.ok(mdx.includes(`title: "Como calcular alíquota CBS IBS sem erro"`));
  assert.ok(mdx.includes(`slug: "como-calcular-aliquota-cbs-ibs"`));
  assert.ok(mdx.includes(`coverImage: "https://cdn.example/img.webp"`));
  assert.ok(mdx.includes(`soroGuid: "4aa3737a-e38b-4624-a082-2472b7b92a70"`));
  assert.ok(mdx.includes("legalRefs: []"));
  assert.ok(mdx.includes("tags: []"));
  assert.ok(mdx.includes("REVISAR antes do merge"));
  assert.ok(mdx.includes("<p>Texto do artigo"));
});

test("#349 feed vazio (só publicados, nenhum) → nenhum post", () => {
  assert.equal(parseFeedToPosts("<rss><channel></channel></rss>").length, 0);
});

test("#349 slugify normaliza acentos e símbolos", () => {
  assert.equal(slugify("Reforma Tributária: CBS & IBS!"), "reforma-tributaria-cbs-ibs");
});
