/**
 * Link-checker interno (#659, L2.3 do Lote 2).
 *
 * O QA registrou que um checador genérico "teria pego o slug 404 e o /support
 * fantasma". Em 17/08 ele teria pego também os três links do rodapé para a área
 * logada (#645) — que só apareceram porque escrevi um guard específico de
 * rodapé. Guard por superfície cobre uma superfície; este cobre a classe.
 *
 * Valida todo href interno do código e dos posts contra as rotas que existem de
 * fato em `src/app` e contra os slugs de `content/blog`.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url)); // frontend/src/lib/seo
const SRC = join(here, "..", "..");
const APP = join(SRC, "app");
const BLOG = join(SRC, "..", "content", "blog");

/** Arquivos servidos fora do app router (route handlers, estáticos do public/). */
const FORA_DO_APP_ROUTER = new Set([
  "/robots.txt",
  "/sitemap.xml",
  "/blog/feed.xml",
]);

function walk(dir: string, exts: RegExp): string[] {
  if (!existsSync(dir)) return [];
  const out: string[] = [];
  for (const e of readdirSync(dir)) {
    const full = join(dir, e);
    if (statSync(full).isDirectory()) out.push(...walk(full, exts));
    else if (exts.test(e)) out.push(full);
  }
  return out;
}

/** Rotas declaradas pelo app router — um diretório com page.tsx vira uma rota. */
function rotasDoApp(): { estaticas: Set<string>; dinamicas: RegExp[] } {
  const estaticas = new Set<string>(FORA_DO_APP_ROUTER);
  const dinamicas: RegExp[] = [];
  for (const page of walk(APP, /^page\.tsx?$/)) {
    const rel = dirname(page).slice(APP.length).replace(/\\/g, "/");
    // Route groups `(grupo)` não aparecem na URL.
    const rota = rel.replace(/\/\([^/]+\)/g, "") || "/";
    if (rota.includes("[")) {
      // `/blog/[slug]` → aceita qualquer segmento naquela posição.
      dinamicas.push(new RegExp("^" + rota.replace(/\[[^\]]+\]/g, "[^/]+") + "$"));
    } else {
      estaticas.add(rota);
    }
  }
  return { estaticas, dinamicas };
}

function slugsDoBlog(): Set<string> {
  return new Set(
    walk(BLOG, /\.mdx?$/).map((f) => "/blog/" + f.split("/").pop()!.replace(/\.mdx?$/, "")),
  );
}

/** Extrai hrefs internos de um arquivo (JSX, objeto de config e markdown). */
function hrefsDe(conteudo: string): string[] {
  const achados: string[] = [];
  const padroes = [
    /href=["'](\/[^"'#?]*)["']/g, // <a href="/x">, <Link href="/x">
    /href:\s*["'](\/[^"'#?]*)["']/g, // { href: "/x" }
    /\]\((\/[^)\s#?]*)\)/g, // [texto](/x) em MDX
  ];
  for (const rx of padroes) {
    for (const m of conteudo.matchAll(rx)) achados.push(m[1]);
  }
  return achados;
}

function normalizar(h: string): string {
  const semBarra = h.length > 1 ? h.replace(/\/+$/, "") : h;
  return semBarra || "/";
}

test("todo link interno aponta para rota que existe", () => {
  const { estaticas, dinamicas } = rotasDoApp();
  const slugs = slugsDoBlog();
  assert.ok(estaticas.size > 20, `rotas carregadas (${estaticas.size})`);

  const arquivos = [...walk(SRC, /\.tsx?$/), ...walk(BLOG, /\.mdx?$/)].filter(
    (f) => !/\.test\.tsx?$/.test(f),
  );

  const quebrados: string[] = [];
  for (const arquivo of arquivos) {
    const rel = arquivo.slice(arquivo.indexOf("frontend/") + 9);
    for (const bruto of hrefsDe(readFileSync(arquivo, "utf-8"))) {
      const h = normalizar(bruto);
      if (h.startsWith("/api/")) continue; // API vive em outro host
      if (estaticas.has(h) || slugs.has(h)) continue;
      if (dinamicas.some((rx) => rx.test(h))) continue;
      quebrados.push(`${rel}: ${bruto}`);
    }
  }

  assert.deepEqual(
    quebrados,
    [],
    "link interno para rota inexistente:\n" + quebrados.map((q) => `  • ${q}`).join("\n"),
  );
});

test("o checador enxerga as rotas reais e os slugs do blog", () => {
  const { estaticas, dinamicas } = rotasDoApp();
  const slugs = slugsDoBlog();
  // Sanidade do próprio checador: se a varredura quebrar, ele passaria vazio.
  for (const r of ["/", "/pricing", "/contato", "/data-policy", "/calculadora"]) {
    assert.ok(estaticas.has(r), `rota ${r} deveria ser reconhecida`);
  }
  assert.ok(slugs.size > 5, `slugs do blog carregados (${slugs.size})`);
  assert.ok(dinamicas.some((rx) => rx.test("/blog/qualquer-coisa")), "rota dinâmica do blog");
});

test("link para rota inexistente é reprovado", () => {
  const { estaticas, dinamicas } = rotasDoApp();
  const slugs = slugsDoBlog();
  const inventada = "/rota-que-nao-existe-123";
  assert.ok(
    !estaticas.has(inventada) && !slugs.has(inventada) && !dinamicas.some((rx) => rx.test(inventada)),
    "o checador precisa reprovar rota inventada — senão passa verde sem servir",
  );
});
