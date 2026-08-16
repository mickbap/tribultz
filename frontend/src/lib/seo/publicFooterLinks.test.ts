/**
 * Guard do rodapé público (#636, L1.6).
 *
 * O rodapé linkava "Suporte" para `/support`, que é página da ÁREA LOGADA:
 * client component chamando `apiFetch`, sem chrome público. O visitante
 * deslogado carregava 200 e via as chamadas autenticadas falharem — o
 * "200 login-like" registrado pelo diagnóstico externo.
 *
 * A propriedade que interessa não é "existe /support"; é: **todo link interno
 * do rodapé público leva a uma página que um visitante deslogado consegue usar**.
 * Ao escrever o guard nesses termos, apareceram outros três links com o mesmo
 * defeito — ver allowlist abaixo.
 *
 * Heurística de "página pública": renderiza `PublicNavbar`/`PublicFooter` em
 * algum arquivo da rota, ou usa `LegalPageLayout` (que os embute). Páginas da
 * área logada não têm chrome próprio — vivem dentro do `AppShell` do layout
 * raiz e dependem de token.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url)); // frontend/src/lib/seo
const SRC = join(here, "..", "..");
const FOOTER = join(SRC, "components", "public", "PublicFooter.tsx");
const LEGAL = join(SRC, "lib", "legal.ts");

/**
 * Dívida conhecida, com issue aberta: #645.
 *
 * Estes três são páginas da área logada linkadas na coluna "Produto". Não
 * entraram no #636 porque o destino correto para um visitante deslogado é
 * decisão de produto (diagnóstico? pricing? landing por recurso?), não conserto
 * mecânico. Ficam listados para a dívida ser visível e o guard seguir barrando
 * ocorrências NOVAS.
 */
const PENDENTES_ISSUE_645 = new Set(["/validate-xml", "/validate-sped", "/compliance"]);

function hrefsInternos(): string[] {
  const fontes = [readFileSync(FOOTER, "utf-8"), readFileSync(LEGAL, "utf-8")].join("\n");
  const achados = [...fontes.matchAll(/href:?\s*[=:]?\s*["'](\/[a-z0-9/-]*)["']/gi)].map((m) => m[1]);
  return [...new Set(achados)].filter((h) => h !== "/");
}

function temChromePublico(rota: string): boolean {
  const dir = join(SRC, "app", rota.replace(/^\//, ""));
  if (!existsSync(dir)) return false;
  return readdirSync(dir)
    .filter((f) => /\.tsx?$/.test(f))
    .some((f) => {
      const src = readFileSync(join(dir, f), "utf-8");
      return /PublicNavbar|PublicFooter|LegalPageLayout/.test(src);
    });
}

test("todo link interno do rodapé aponta para rota existente", () => {
  const quebrados = hrefsInternos().filter(
    (h) => !existsSync(join(SRC, "app", h.replace(/^\//, ""))),
  );
  assert.deepEqual(quebrados, [], `rodapé aponta para rota inexistente: ${quebrados.join(", ")}`);
});

test("todo link interno do rodapé leva a página utilizável por visitante deslogado", () => {
  const privados = hrefsInternos()
    .filter((h) => !PENDENTES_ISSUE_645.has(h))
    .filter((h) => !temChromePublico(h));

  assert.deepEqual(
    privados,
    [],
    "rodapé público linkando página da área logada — visitante deslogado vê chamadas autenticadas falharem:\n" +
      privados.map((p) => `  • ${p}`).join("\n"),
  );
});

test("/support saiu do rodapé público (é área logada)", () => {
  const footer = readFileSync(FOOTER, "utf-8");
  assert.ok(
    !/href="\/support"/.test(footer),
    "`/support` é página autenticada; o rodapé público deve apontar para /contato",
  );
  assert.match(footer, /href="\/contato"/);
});

test("a allowlist só contém o que a issue #645 cobre", () => {
  // Se alguém acrescentar uma rota aqui sem tratar a dívida, o número de
  // pendências cresce silenciosamente. Este teste congela o tamanho.
  assert.equal(PENDENTES_ISSUE_645.size, 3);
});

test("/contato declara canonical próprio e é público", async () => {
  const m = (await import("../../app/contato/page")) as {
    metadata?: { alternates?: { canonical?: unknown } };
  };
  assert.equal(m.metadata?.alternates?.canonical, "/contato");
  assert.ok(temChromePublico("/contato"));
});
