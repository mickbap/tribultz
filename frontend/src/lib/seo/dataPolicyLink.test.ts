/**
 * Guard do link da política de dados (#637, L1.7).
 *
 * `schemas.ts` mandava o leitor para `/api/v1/public/data-policy` — caminho
 * RELATIVO. A API vive em host próprio (`api.tribultz.com.br`); no domínio do
 * site esse caminho resolve para o apex e devolve 404. Como a frase vive numa
 * resposta de FAQ em JSON-LD, que o Google pode exibir como rich result, quem
 * clicasse caía num 404.
 *
 * O guard é sobre a classe do defeito, não sobre a string: nenhuma copy de
 * JSON-LD pode apontar caminho de API relativo. Caminhos relativos em código de
 * fetch continuam legítimos (são concatenados a `API_BASE`) — por isso a
 * varredura é restrita aos schemas, que são texto para leitor.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url)); // frontend/src/lib/seo
const SCHEMAS = join(here, "..", "..", "components", "seo", "schemas.ts");

test("copy de JSON-LD não manda o leitor navegar até caminho de API relativo", () => {
  const src = readFileSync(SCHEMAS, "utf-8");

  // Só interessa o caminho apresentado como DESTINO para o leitor ("… em
  // /api/v1/…"). Citar um endpoint ao descrever a API para desenvolvedor
  // ("O endpoint POST /api/v1/public_api/calculate retorna …") é legítimo:
  // ninguém clica, e o path relativo é a forma correta de documentar rota.
  const navegacional = /\b(?:em|acesse|consulte|disponível\s+em)\s+(\/api\/v\d[^\s".,)]*)/gi;

  const achados = [...src.matchAll(navegacional)].map((m) => m[1]);
  assert.deepEqual(
    achados,
    [],
    "caminho de API relativo oferecido como destino resolve para o apex e 404a:\n" +
      achados.map((r) => `  • ${r}`).join("\n"),
  );
});

test("a resposta de FAQ aponta para a página do site, não para JSON cru", () => {
  const src = readFileSync(SCHEMAS, "utf-8");
  assert.match(
    src,
    /Veja a política completa em \$\{SITE_URL\}\/data-policy/,
    "o FAQ deve levar à página /data-policy do próprio site",
  );
});

test("/data-policy está no sitemap", () => {
  const sitemap = readFileSync(join(here, "..", "..", "app", "sitemap.ts"), "utf-8");
  assert.match(sitemap, /\/data-policy/);
});

test("/data-policy declara canonical próprio", async () => {
  const m = (await import("../../app/data-policy/page")) as {
    metadata?: { alternates?: { canonical?: unknown } };
  };
  assert.equal(m.metadata?.alternates?.canonical, "/data-policy");
});
