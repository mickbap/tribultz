/**
 * Guard de fonte única da contagem de regras (#631, L1.1 do Lote 1).
 *
 * `RULES_COUNT` (rulesMeta.ts) é a fonte canônica. Mesmo assim, o /diagnostico
 * exibia "18" em literal — na MESMA página que já importava a constante e a
 * usava corretamente noutra linha. O site anunciava 35 e 18 ao mesmo tempo.
 *
 * O detalhe que fez o defeito sobreviver: número e substantivo estavam em
 * elementos JSX separados —
 *
 *     <p className="text-3xl ...">18</p>
 *     <p className="mt-1 ...">
 *       regras fiscais verificadas conforme NT 2025.002-RTC
 *     </p>
 *
 * — de modo que um grep de /\d+ regras/ no fonte não casava. Por isso este
 * guard varre em duas passadas: o texto cru (pega o caso inline e atributos) e
 * o texto sem tags (pega o caso partido entre elementos).
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOTS = ["src/app", "src/components"];

/** Substantivos que caracterizam uma contagem de regras do motor. */
const COUNT_NOUN = "regras";

/** Contextos onde um número seguido de "regras" NÃO é a contagem do motor. */
const ALLOWED_CONTEXT = [
  /\d+\s+regras\s+alteradas/i,   // "~22 regras alteradas pela NT v1.51"
  /\d+\s+regras\s+novas/i,       // "8 regras novas" (escopo de uma NT futura)
  /\d+\s+regras\s+violadas/i,    // "Top 3 Regras Violadas" — tamanho da lista, não do motor
];

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...walk(full));
    } else if (/\.(tsx?|mdx?)$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

/** Remove tags JSX/HTML e colapsa espaço — junta número e substantivo separados. */
function stripTags(source: string): string {
  return source.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");
}

function offendingMatches(text: string): string[] {
  const re = new RegExp(String.raw`(\d+)\s+${COUNT_NOUN}\b[^.\n]{0,40}`, "gi");
  const hits: string[] = [];
  for (const m of text.matchAll(re)) {
    const snippet = m[0].trim();
    if (ALLOWED_CONTEXT.some((rx) => rx.test(snippet))) continue;
    hits.push(snippet);
  }
  return hits;
}

test("contagem de regras nunca aparece como literal na superfície pública", () => {
  const offenders: string[] = [];

  for (const root of ROOTS) {
    for (const file of walk(join(process.cwd(), root))) {
      const raw = readFileSync(file, "utf8");
      const rel = file.slice(process.cwd().length + 1);

      // Passada 1 — texto cru: pega "18 regras" inline e dentro de atributos.
      for (const hit of offendingMatches(raw)) {
        offenders.push(`${rel}: ${hit}`);
      }
      // Passada 2 — sem tags: pega o número separado do substantivo por JSX.
      for (const hit of offendingMatches(stripTags(raw))) {
        const entry = `${rel}: ${hit}`;
        if (!offenders.includes(entry)) offenders.push(entry);
      }
    }
  }

  assert.deepEqual(
    offenders,
    [],
    `Contagem de regras em literal — use RULES_COUNT de @/lib/validation/rulesMeta:\n` +
      offenders.map((o) => `  • ${o}`).join("\n"),
  );
});

test("o guard reconhece o formato partido entre elementos JSX", () => {
  // Regressão do próprio guard: se alguém simplificar para um grep de /\d+ regras/
  // no texto cru, este caso volta a passar despercebido.
  const partido = `
    <p className="text-3xl font-extrabold">18</p>
    <p className="mt-1 text-sm">
      regras fiscais verificadas conforme NT 2025.002-RTC
    </p>`;
  assert.equal(offendingMatches(partido).length, 0, "no texto cru não deve casar");
  assert.ok(offendingMatches(stripTags(partido)).length > 0, "sem tags deve casar");
});

test("o guard aceita a contagem vinda da constante", () => {
  const correto = `<span>{RULES_COUNT} regras verificadas</span>`;
  assert.deepEqual(offendingMatches(correto), []);
  assert.deepEqual(offendingMatches(stripTags(correto)), []);
});
