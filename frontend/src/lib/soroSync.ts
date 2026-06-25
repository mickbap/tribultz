/**
 * Soro RSS → MDX (#349). Converte o feed RSS do Soro em posts MDX do nosso blog,
 * para entrarem via PR com revisão humana (gate). Fonte controlada (feed do Soro,
 * RSS 2.0 + content:encoded + media:content); parsing direcionado às tags conhecidas.
 *
 * Importante: NADA aqui publica — só gera o conteúdo do arquivo. A publicação acontece
 * apenas quando o PR (needs-review) é mergeado por um humano.
 */

export type SoroPost = {
  guid: string;
  title: string;
  description: string;
  slug: string;
  link: string;
  publishedAt: string; // ISO 8601
  coverImage?: string;
  contentHtml: string;
};

function decodeEntities(s: string): string {
  return s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&");
}

function tagValue(item: string, name: string): string | undefined {
  const re = new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)</${name}>`);
  const m = item.match(re);
  if (!m) return undefined;
  const raw = m[1].trim();
  const cdata = raw.match(/^<!\[CDATA\[([\s\S]*?)\]\]>$/);
  return cdata ? cdata[1] : decodeEntities(raw);
}

function tagAttr(item: string, name: string, attr: string): string | undefined {
  const re = new RegExp(`<${name}[^>]*\\b${attr}="([^"]*)"`);
  return item.match(re)?.[1];
}

export function slugify(input: string): string {
  return input
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function slugFromLink(link: string, title: string): string {
  try {
    const last = new URL(link).pathname.replace(/\/+$/, "").split("/").filter(Boolean).pop();
    if (last) return last;
  } catch {
    /* link inválido → cai no slug do título */
  }
  return slugify(title);
}

function toIso(rfc822: string | undefined): string {
  const d = new Date(rfc822 ?? "");
  return Number.isNaN(d.getTime()) ? new Date().toISOString() : d.toISOString();
}

export function parseFeedToPosts(xml: string): SoroPost[] {
  const items = xml.match(/<item>[\s\S]*?<\/item>/g) ?? [];
  return items.map((item) => {
    const title = tagValue(item, "title") ?? "Sem título";
    const link = tagValue(item, "link") ?? "";
    const description = tagValue(item, "description") ?? "";
    return {
      guid: tagValue(item, "guid") ?? link ?? title,
      title,
      description,
      slug: slugFromLink(link, title),
      link,
      publishedAt: toIso(tagValue(item, "pubDate")),
      coverImage: tagAttr(item, "media:content", "url") ?? tagAttr(item, "enclosure", "url"),
      contentHtml: tagValue(item, "content:encoded") ?? description,
    };
  });
}

const EDITORIAL_AUTHOR = {
  name: "Equipe Tribultz",
  jobTitle: "Conteúdo Fiscal",
  url: "https://tribultz.com.br/sobre",
};

const yamlStr = (s: string) => `"${s.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;

/** Escapa chaves para não quebrar a compilação MDX (artigos raramente usam `{`/`}`). */
const mdxSafe = (html: string) => html.replace(/{/g, "&#123;").replace(/}/g, "&#125;");

export function postToMdx(p: SoroPost): { filename: string; mdx: string } {
  const lines = [
    "---",
    `title: ${yamlStr(p.title)}`,
    `description: ${yamlStr(p.description)}`,
    `slug: ${yamlStr(p.slug)}`,
    `category: "Reforma Tributária"`,
    "author:",
    `  name: ${yamlStr(EDITORIAL_AUTHOR.name)}`,
    `  jobTitle: ${yamlStr(EDITORIAL_AUTHOR.jobTitle)}`,
    `  url: ${yamlStr(EDITORIAL_AUTHOR.url)}`,
    `publishedAt: ${yamlStr(p.publishedAt)}`,
    "tags: []",
    ...(p.coverImage ? [`coverImage: ${yamlStr(p.coverImage)}`] : []),
    "legalRefs: []",
    `soroGuid: ${yamlStr(p.guid)}`,
    "---",
    "",
    "{/* Gerado pelo Soro — REVISAR antes do merge: precisão fiscal, legalRefs, tags, category. */}",
    "",
    mdxSafe(p.contentHtml).trim(),
    "",
  ];
  return { filename: `${p.slug}.mdx`, mdx: lines.join("\n") };
}
