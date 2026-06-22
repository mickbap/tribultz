import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { RULES_COUNT, PLACEHOLDER_RULE_IDS } from "./rulesMeta";

// Guarda anti-drift (RF-1): RULES_COUNT deve igualar a contagem real de regras de
// validação ativas no engine (ruleIds distintos do xmlRules.ts menos os placeholders).
// Se uma regra for adicionada/removida no engine, este teste falha até RULES_COUNT
// ser atualizado — garantindo que site/blog/metadados nunca divirjam do código.
test("RULES_COUNT == regras ativas no engine (xmlRules.ts)", () => {
  const src = readFileSync(join(process.cwd(), "src/lib/validation/xmlRules.ts"), "utf-8");
  const ids = new Set<string>();
  for (const m of src.matchAll(/ruleId:\s*"([A-Z_]+)"/g)) {
    ids.add(m[1]);
  }
  const placeholders = new Set(PLACEHOLDER_RULE_IDS);
  const active = [...ids].filter((id) => !placeholders.has(id));
  assert.equal(
    active.length,
    RULES_COUNT,
    `RULES_COUNT (${RULES_COUNT}) ≠ regras ativas no engine (${active.length}). ` +
      `ruleIds ativos: ${active.sort().join(", ")}. Atualize RULES_COUNT em rulesMeta.ts.`,
  );
});

test("placeholders existem no engine (evita exclusão obsoleta)", () => {
  const src = readFileSync(join(process.cwd(), "src/lib/validation/xmlRules.ts"), "utf-8");
  for (const ph of PLACEHOLDER_RULE_IDS) {
    assert.ok(src.includes(`"${ph}"`), `placeholder ${ph} não encontrado no engine — remover de PLACEHOLDER_RULE_IDS`);
  }
});
