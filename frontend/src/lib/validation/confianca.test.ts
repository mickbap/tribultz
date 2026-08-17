/**
 * #660 (L2.4) — limiares de confiança em fonte única.
 *
 * Os valores já eram coerentes; o problema era dispersão: viviam soltos em
 * resposta de FAQ e no badge do widget, cada um escrito à mão. Este guard
 * impede que voltem a ser literais — mesma família do de RULES_COUNT e do Trial.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  CONFIANCA_ALTA,
  CONFIANCA_ALTA_PCT,
  CONFIANCA_MINIMA,
  CONFIANCA_MINIMA_PCT,
  REGUA_CONFIANCA,
  faixaDeConfianca,
} from "./confianca";

const here = dirname(fileURLToPath(import.meta.url));
const CLASSIFICACAO = join(here, "..", "..", "app", "classificacao");

test("as faixas cobrem o intervalo sem buraco nem sobreposição", () => {
  assert.equal(faixaDeConfianca(1), "alta");
  assert.equal(faixaDeConfianca(CONFIANCA_ALTA), "alta");
  assert.equal(faixaDeConfianca(CONFIANCA_ALTA - 0.001), "media");
  assert.equal(faixaDeConfianca(CONFIANCA_MINIMA), "media");
  assert.equal(faixaDeConfianca(CONFIANCA_MINIMA - 0.001), "baixa");
  assert.equal(faixaDeConfianca(0), "baixa");
});

test("a régua visível tem uma linha por faixa, sem lacuna", () => {
  assert.deepEqual(
    REGUA_CONFIANCA.map((f) => f.faixa),
    ["alta", "media", "baixa"],
  );
  for (const f of REGUA_CONFIANCA) {
    assert.ok(f.rotulo.trim() && f.acao.trim(), `faixa ${f.faixa} precisa de rótulo e ação`);
  }
});

test("nenhuma faixa promete autorização automática", () => {
  // O parecer registrou que não há tal promessa hoje; o guard impede que apareça.
  const proibido = /autoriza|aprovad|garant|pode emitir sem/i;
  for (const f of REGUA_CONFIANCA) {
    assert.ok(!proibido.test(f.acao), `faixa ${f.faixa} não pode prometer aprovação: "${f.acao}"`);
  }
});

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir)) {
    const full = join(dir, e);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.tsx?$/.test(e)) out.push(full);
  }
  return out;
}

test("limiar não volta a aparecer como literal na página de classificação", () => {
  const infratores: string[] = [];
  for (const arquivo of walk(CLASSIFICACAO)) {
    const raw = readFileSync(arquivo, "utf-8");
    const rel = arquivo.slice(arquivo.indexOf("src/"));
    // Literal de percentual (70%/85%) ou de fração (0.70/0.85) junto de "confian".
    for (const rx of [
      new RegExp(`\\b${CONFIANCA_MINIMA_PCT}%`),
      new RegExp(`\\b${CONFIANCA_ALTA_PCT}%`),
      new RegExp(`\\b0\\.${String(CONFIANCA_MINIMA).slice(2)}\\b`),
      new RegExp(`\\b0\\.${String(CONFIANCA_ALTA).slice(2)}\\b`),
    ]) {
      const m = rx.exec(raw);
      if (m) infratores.push(`${rel}: "${m[0]}"`);
    }
  }
  assert.deepEqual(
    infratores,
    [],
    "limiar de confiança em literal — derive de @/lib/validation/confianca:\n" +
      infratores.map((i) => `  • ${i}`).join("\n"),
  );
});
