import assert from "node:assert/strict";
import test from "node:test";
import { resolveRuleEnforcement } from "./ruleEnforcement";

test("schema, RV e homologacao nao implicam enforcement em producao", () => {
  const state = resolveRuleEnforcement("NFE", "DANFE_SIMPLIFICADO_RESTRICAO", "1.00", "2026-07-15");
  assert.ok(state);
  assert.equal(state.schema_supported, true);
  assert.equal(state.validation_rule_defined, true);
  assert.equal(state.homologation_enforced, true);
  assert.equal(state.legal_required, false);
  assert.equal(state.production_enforced, false);
});

test("vigencia ativa somente os marcos datados", () => {
  const state = resolveRuleEnforcement("NFE", "DANFE_SIMPLIFICADO_RESTRICAO", "1.00", "2026-08-03");
  assert.ok(state);
  assert.equal(state.legal_required, true);
  assert.equal(state.production_enforced, true);
  assert.equal(state.effective_from.schema_supported, null);
});

test("tipo documental e versao fazem parte da chave", () => {
  assert.equal(resolveRuleEnforcement("NFCE", "DANFE_SIMPLIFICADO_RESTRICAO", "1.00", "2026-08-03"), undefined);
  assert.equal(resolveRuleEnforcement("NFE", "DANFE_SIMPLIFICADO_RESTRICAO", "1.10a", "2026-08-03"), undefined);
});

test("data civil invalida nao resolve vigencia", () => {
  assert.equal(resolveRuleEnforcement("NFE", "DANFE_SIMPLIFICADO_RESTRICAO", "1.00", "2026-02-31"), undefined);
});
