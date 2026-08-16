/**
 * Guard de canonical por rota (#634, L1.4 do Lote 1).
 *
 * O layout raiz fixava `alternates: { canonical: SITE_URL }`. Toda rota que não
 * sobrescrevesse herdava o canonical da HOME — o site inteiro se declarando
 * duplicata da home para o indexador. Falha silenciosa: a página renderiza
 * normalmente, só o sinal de SEO sai errado.
 *
 * Este teste importa os módulos de metadata de verdade e confere o valor
 * resolvido — não é varredura de texto. Como `metadataBase` vive no layout
 * raiz, os canonical são relativos e o Next os resolve contra ele.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url)); // frontend/src/lib/seo

/** Rota pública → caminho do módulo que declara seu metadata. */
const ROTAS: Array<[string, string]> = [
  ["/", "../../app/page"],
  ["/calculadora", "../../app/calculadora/layout"],
  ["/classificacao", "../../app/classificacao/layout"],
  ["/compliance", "../../app/compliance/layout"],
  ["/diagnostico", "../../app/diagnostico/layout"],
  ["/pricing", "../../app/pricing/layout"],
  ["/split-payment", "../../app/split-payment/layout"],
  ["/changelog", "../../app/changelog/page"],
  ["/cookies", "../../app/cookies/page"],
  ["/founding-partners", "../../app/founding-partners/page"],
  ["/lgpd", "../../app/lgpd/page"],
  ["/privacy", "../../app/privacy/page"],
  ["/refund-policy", "../../app/refund-policy/page"],
  ["/simulador", "../../app/simulador/page"],
  ["/terms", "../../app/terms/page"],
];

async function canonicalDe(mod: string): Promise<unknown> {
  const m = (await import(mod)) as { metadata?: { alternates?: { canonical?: unknown } } };
  return m.metadata?.alternates?.canonical;
}

test("toda rota pública declara o próprio canonical", async () => {
  for (const [rota, mod] of ROTAS) {
    const canonical = await canonicalDe(mod);
    assert.equal(
      canonical,
      rota,
      `${rota} deveria declarar canonical "${rota}", declara ${JSON.stringify(canonical)}`,
    );
  }
});

test("nenhuma rota pública compartilha canonical com outra", async () => {
  const vistos = new Map<string, string>();
  for (const [rota, mod] of ROTAS) {
    const canonical = String(await canonicalDe(mod));
    const anterior = vistos.get(canonical);
    assert.equal(
      anterior,
      undefined,
      `${rota} e ${anterior} declaram o mesmo canonical "${canonical}" — provável copy-paste`,
    );
    vistos.set(canonical, rota);
  }
});

test("o layout raiz não fixa canonical global", () => {
  // Único caso checado no fonte, e não por import: `app/layout.tsx` faz
  // `import "./globals.css"`, que o runner do Node não parseia. A asserção é
  // sobre a AUSÊNCIA de uma chave, então ler o fonte basta — e é mais honesto
  // do que mockar o CSS só para reintroduzir o import.
  const src = readFileSync(join(here, "..", "..", "app", "layout.tsx"), "utf-8");
  const dentroDeMetadata = src.slice(
    src.indexOf("export const metadata"),
    src.indexOf("export default function RootLayout"),
  );
  const declaracoes = dentroDeMetadata
    .split("\n")
    .filter((l) => /canonical/.test(l) && !/^\s*(\/\/|\*|\/\*)/.test(l));
  assert.deepEqual(
    declaracoes,
    [],
    "canonical global no layout raiz faz toda rota sem override herdar o da home (#634)",
  );
});

test("o blog mantém canonical próprio (não regride para o da home)", async () => {
  const canonical = await canonicalDe("../../app/blog/page");
  assert.match(String(canonical), /\/blog$/);
});
