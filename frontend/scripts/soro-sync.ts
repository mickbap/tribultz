/**
 * Soro RSS → MDX (#349). Executado pela GitHub Action `soro-blog-sync.yml`.
 * Lê o feed (SORO_RSS_URL), gera .mdx para itens novos (dedup por slug) e os grava
 * em content/blog/. A Action abre um PR draft (needs-review) com os arquivos — nada
 * vai ao ar sem revisão + merge humano.
 *
 * Rodar local: SORO_RSS_URL="..." npx tsx scripts/soro-sync.ts   (a partir de frontend/)
 */
import fs from "node:fs";
import path from "node:path";
import { parseFeedToPosts, postToMdx } from "../src/lib/soroSync";
import { lintMdx } from "../src/lib/contentLint";

const FEED_URL = process.env.SORO_RSS_URL;
const CONTENT_DIR = path.join(process.cwd(), "content", "blog");

async function main() {
  if (!FEED_URL) {
    console.error("SORO_RSS_URL não definido.");
    process.exit(1);
  }
  const res = await fetch(FEED_URL);
  if (!res.ok) {
    console.error(`Feed indisponível: HTTP ${res.status}`);
    process.exit(1);
  }
  const posts = parseFeedToPosts(await res.text());
  fs.mkdirSync(CONTENT_DIR, { recursive: true });

  let created = 0;
  for (const p of posts) {
    const built = postToMdx(p);
    const dest = path.join(CONTENT_DIR, built.filename);
    if (fs.existsSync(dest)) {
      console.log(`skip (já existe): ${built.filename}`);
      continue;
    }
    // Corretor de conformidade: auto-fix do determinístico (ex.: alíquota plena sem
    // contexto de 2026) + flags para a revisão humana do PR.
    const { mdx, findings } = lintMdx(built.mdx);
    fs.writeFileSync(dest, mdx, "utf-8");
    console.log(`novo: ${built.filename}`);
    for (const f of findings) {
      console.log(`   [${f.severity === "fix" ? "auto-fix" : "REVISAR"}] ${f.rule}: ${f.message}`);
    }
    created++;
  }
  console.log(`Itens no feed: ${posts.length} | novos gravados: ${created}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
