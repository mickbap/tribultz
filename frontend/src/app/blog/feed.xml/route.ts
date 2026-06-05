import { getAllPosts } from "@/lib/blog";

const SITE_URL = "https://tribultz.com.br";

export const dynamic = "force-static";

export function GET() {
  const posts = getAllPosts();
  const lastBuild = posts[0]?.publishedAt ?? new Date().toISOString();

  const items = posts
    .map((post) => {
      const url = `${SITE_URL}/blog/${post.slug}`;
      return `
    <item>
      <title><![CDATA[${post.title}]]></title>
      <link>${url}</link>
      <guid isPermaLink="true">${url}</guid>
      <description><![CDATA[${post.description}]]></description>
      <pubDate>${new Date(post.publishedAt + "T00:00:00").toUTCString()}</pubDate>
      <author>${post.author.name}</author>
      ${post.tags.map((t) => `<category>${t}</category>`).join("\n      ")}
    </item>`.trim();
    })
    .join("\n  ");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Tribultz Blog — Reforma Tributária CBS/IBS</title>
    <link>${SITE_URL}/blog</link>
    <description>Artigos técnicos sobre cClassTrib, NCM, CBS/IBS e a Reforma Tributária de 2026.</description>
    <language>pt-BR</language>
    <lastBuildDate>${new Date(lastBuild + "T00:00:00").toUTCString()}</lastBuildDate>
    <atom:link href="${SITE_URL}/blog/feed.xml" rel="self" type="application/rss+xml"/>
    ${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600, s-maxage=3600",
    },
  });
}
