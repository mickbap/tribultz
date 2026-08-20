/**
 * Item 9 da régua do Trial (#635): fonte única verificável.
 *
 * "Teste que falha se qualquer superfície declarar número/prazo de trial fora
 * da config canônica."
 *
 * A verificação frontend↔backend (`trial.ts` espelha `trial_policy.json`) vive
 * no backend, em `test_trial_regua.py`. Aqui o alvo é a COPY: os números do
 * Trial não podem voltar a ser escritos à mão em página nenhuma.
 *
 * `\\S*` e não `\\w+` de propósito: em JS, `\\w` é [A-Za-z0-9_] e NÃO casa
 * acento — `valida\\w+` falhava justamente em "validações". O guard passava
 * verde sem servir para nada; só a prova empírica revelou.
 *
 * Limite conhecido do guard: ele proíbe os literais do Trial, não qualquer
 * número perto da palavra "validações" — `/pricing` legitimamente escreve "10
 * validações XML por mês", "500 …" e "2.000 …" para os planos pagos, que não
 * são governados por esta política.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  TRIAL_FEATURES,
  TRIAL_DURATION_DAYS,
  TRIAL_DURATION_LABEL,
  TRIAL_QUOTA_LABEL,
  TRIAL_QUOTA_PERIOD,
  TRIAL_VALIDATION_QUOTA,
} from "./trial";

const here = dirname(fileURLToPath(import.meta.url)); // frontend/src/lib
const APP = join(here, "..", "app");
const SELF = join(here, "trial.ts");

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir)) {
    const full = join(dir, e);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.tsx?$/.test(e)) out.push(full);
  }
  return out;
}

/** Literais que só podem existir derivados das constantes. */
const PROIBIDOS: Array<[RegExp, string]> = [
  [new RegExp(`\\b${TRIAL_VALIDATION_QUOTA}\\s+valida\\S*`, "i"), "use TRIAL_QUOTA_LABEL"],
  [new RegExp(`Gr[áa]tis por ${TRIAL_DURATION_DAYS} dias`, "i"), "use TRIAL_DURATION_LABEL"],
];

test("nenhuma superfície escreve o número ou o prazo do Trial à mão", () => {
  const infratores: string[] = [];
  for (const file of walk(APP)) {
    if (file === SELF) continue;
    const raw = readFileSync(file, "utf-8");
    const rel = file.slice(file.indexOf("src/"));
    for (const [rx, dica] of PROIBIDOS) {
      const m = rx.exec(raw);
      if (m) infratores.push(`${rel}: "${m[0]}" — ${dica}`);
    }
  }
  assert.deepEqual(
    infratores,
    [],
    "número/prazo do Trial em literal — derive de @/lib/trial:\n" +
      infratores.map((i) => `  • ${i}`).join("\n"),
  );
});

test("a franquia do Trial nunca é apresentada como mensal", () => {
  // A decisão de Produto é explícita: `quota_period = trial_lifetime`. O
  // /pricing dizia "5 validações XML POR MÊS", que é o contrato de outro plano.
  assert.equal(TRIAL_QUOTA_PERIOD, "trial_lifetime");
  assert.ok(
    !/por m[êe]s/i.test(TRIAL_QUOTA_LABEL),
    `rótulo da franquia não pode sugerir recorrência mensal: "${TRIAL_QUOTA_LABEL}"`,
  );

  const infratores: string[] = [];
  for (const file of walk(APP)) {
    const raw = readFileSync(file, "utf-8");
    if (new RegExp(`${TRIAL_VALIDATION_QUOTA}\\s+valida\\S*[^."]{0,20}por m[êe]s`, "i").test(raw)) {
      infratores.push(file.slice(file.indexOf("src/")));
    }
  }
  assert.deepEqual(infratores, [], `franquia do Trial apresentada como mensal em: ${infratores}`);
});

test("os rótulos derivam mesmo das constantes", () => {
  assert.ok(TRIAL_DURATION_LABEL.includes(String(TRIAL_DURATION_DAYS)));
  assert.ok(TRIAL_QUOTA_LABEL.includes(String(TRIAL_VALIDATION_QUOTA)));
});


// --- Round 13: API não é benefício do Trial ---------------------------------

test("nenhuma superfície apresenta API ou créditos como benefício do Trial", () => {
  // Ordem de Produto de 17/08: `trial.api = false` é definitivo, e nenhuma
  // ocorrência residual pode apresentar API/créditos como parte do Trial.
  //
  // O que existia: a FAQ em JSON-LD do /pricing afirmava "O plano Trial é
  // gratuito e dá acesso a 100 créditos de API e à validação completa de até
  // 20 NF-e" — errado nos DOIS números, e em texto que o Google pode exibir.
  const suspeitos = [
    /Trial[^.]{0,120}cr[ée]ditos?\s+de\s+API/i,
    /Trial[^.]{0,120}acesso\s+[àa]\s+API/i,
    /\d+\s+cr[ée]ditos?\s+API\s+gr[áa]tis/i,
    /cr[ée]ditos?\s+API\s+gr[áa]tis/i,
  ];
  const infratores: string[] = [];
  for (const arquivo of [...walk(APP), join(here, "..", "components", "seo", "schemas.ts")]) {
    const raw = readFileSync(arquivo, "utf-8");
    const rel = arquivo.slice(arquivo.indexOf("src/"));
    for (const rx of suspeitos) {
      const m = rx.exec(raw);
      if (m) infratores.push(`${rel}: "${m[0].slice(0, 70)}"`);
    }
  }
  assert.deepEqual(
    infratores,
    [],
    "API/créditos apresentados como benefício do Trial:\n" +
      infratores.map((i) => `  • ${i}`).join("\n"),
  );
});

test("a política declara API fora do Trial", () => {
  assert.equal(TRIAL_FEATURES.api, false);
  assert.equal(TRIAL_FEATURES.pdf, false);
  assert.equal(TRIAL_FEATURES.dashboard, false);
});
