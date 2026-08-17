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
