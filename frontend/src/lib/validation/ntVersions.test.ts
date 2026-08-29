/**
 * Guards da separação entre versão UPSTREAM (publicada) e versão IMPLEMENTADA.
 *
 * O defeito que originou estes testes: um único campo, `NT_CURRENT_VERSION`,
 * respondia por dois conceitos incompatíveis. O próprio comentário abaixo dele
 * documentava a colisão — v1.51 e v1.10 publicadas e deliberadamente não
 * bumpadas, porque bumpar marcaria ~13 posts corretos como desatualizados. Ou
 * seja: na prática o campo já significava cobertura, mas se chamava "vigente".
 *
 * O risco que estes guards fecham é o inverso do bug original: alguém observa
 * uma publicação upstream e a promove a prova de cobertura do motor.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  NT_IMPLEMENTED_VERSION,
  NT_UPSTREAM_VERSION,
  ntCoverageGap,
} from "./rulesMeta";

const aqui = dirname(fileURLToPath(import.meta.url));
const lintSrc = readFileSync(join(aqui, "..", "blogFiscalLint.ts"), "utf8");

test("blogFiscalLint nunca consome a versão upstream", () => {
  assert.ok(
    lintSrc.includes("NT_IMPLEMENTED_VERSION"),
    "o lint deve citar a versão COBERTA pelo motor",
  );
  assert.ok(
    !lintSrc.includes("NT_UPSTREAM_VERSION"),
    "o lint passou a tratar publicação upstream como prova de cobertura — " +
      "isso marcaria posts corretos como desatualizados",
  );
});

test("os dois mapas são estruturas distintas, não apelidos", () => {
  assert.notEqual(
    JSON.stringify(NT_IMPLEMENTED_VERSION),
    JSON.stringify(NT_UPSTREAM_VERSION),
  );
});

test("NT 2026.002 NÃO está marcada como implementada em 1.10a", () => {
  // A v1.10a foi publicada em 25/08/2026 e o motor não a implementa. Marcar
  // aqui seria afirmar cobertura inexistente.
  assert.notEqual(NT_IMPLEMENTED_VERSION["NT 2026.002"], "1.10a");
  assert.equal(NT_UPSTREAM_VERSION["NT 2026.002"]?.versao, "1.10a");
});

test("toda NT implementada tem contraparte upstream, para a lacuna ser mensurável", () => {
  for (const nt of Object.keys(NT_IMPLEMENTED_VERSION)) {
    assert.ok(
      NT_UPSTREAM_VERSION[nt],
      `${nt} está implementada mas não tem versão upstream observada — ` +
        "a defasagem fica invisível",
    );
  }
});

test("toda observação upstream aponta para o portal oficial", () => {
  for (const [nt, up] of Object.entries(NT_UPSTREAM_VERSION)) {
    assert.ok(
      up.source_url.startsWith("https://www.nfe.fazenda.gov.br/"),
      `${nt}: source_url não é o portal oficial`,
    );
    assert.match(up.observado_em, /^\d{4}-\d{2}-\d{2}$/, `${nt}: observado_em inválido`);
    assert.match(up.publicada_em, /^\d{4}-\d{2}-\d{2}$/, `${nt}: publicada_em inválido`);
  }
});

test("ntCoverageGap expõe a defasagem real observada em 29/08/2026", () => {
  const porNt = Object.fromEntries(ntCoverageGap().map((g) => [g.nt, g]));

  assert.deepEqual(porNt["NT 2025.002"], {
    nt: "NT 2025.002", upstream: "1.51", implementada: "1.40", defasada: true,
  });
  assert.deepEqual(porNt["NT 2026.002"], {
    nt: "NT 2026.002", upstream: "1.10a", implementada: "1.00", defasada: true,
  });
  // NT não coberta em versão nenhuma é estado DISTINTO de coberta numa versão
  // anterior — `implementada: null`, não string vazia.
  assert.equal(porNt["NT 2026.007"].implementada, null);
  assert.equal(porNt["NT 2026.007"].defasada, true);
});
