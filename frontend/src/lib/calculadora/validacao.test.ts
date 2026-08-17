/**
 * #657 (L2.1) — validação client-side da calculadora e teto de espera no fetch.
 *
 * A validação server-side sempre existiu e está correta; faltava a do cliente.
 * As regras aqui espelham `calculadora.py` de propósito — divergir seria pior
 * que não validar.
 */

import test from "node:test";
import assert from "node:assert/strict";

import { temErro, validarCalculadora } from "./validacao";
import { FETCH_TIMEOUT_MS, fetchWithRetry } from "../api";

const ok = { baseValue: "1000.00", quantity: "1", ncm: "" };

test("entrada válida não produz erro", () => {
  assert.deepEqual(validarCalculadora(ok), {});
  assert.equal(temErro(validarCalculadora(ok)), false);
});

test("base precisa ser maior que zero", () => {
  for (const v of ["0", "-5", "abc"]) {
    assert.ok(validarCalculadora({ ...ok, baseValue: v }).baseValue, `base "${v}" deveria falhar`);
  }
  assert.ok(validarCalculadora({ ...ok, baseValue: "" }).baseValue);
});

test("base aceita vírgula decimal", () => {
  assert.deepEqual(validarCalculadora({ ...ok, baseValue: "1000,50" }), {});
});

test("quantidade precisa ser inteiro a partir de 1", () => {
  for (const v of ["0", "-1", "1.5", ""]) {
    assert.ok(validarCalculadora({ ...ok, quantity: v }).quantity, `qtd "${v}" deveria falhar`);
  }
});

test("NCM é opcional, mas quando preenchido tem 8 dígitos", () => {
  assert.deepEqual(validarCalculadora({ ...ok, ncm: "" }), {});
  assert.deepEqual(validarCalculadora({ ...ok, ncm: "84713012" }), {});
  assert.ok(validarCalculadora({ ...ok, ncm: "8471" }).ncm);
  assert.ok(validarCalculadora({ ...ok, ncm: "847130123" }).ncm);
});

test("erros são acumulados, não interrompidos no primeiro", () => {
  const erros = validarCalculadora({ baseValue: "0", quantity: "0", ncm: "123" });
  assert.equal(Object.keys(erros).length, 3, "o usuário deve ver tudo o que precisa corrigir");
});

test("fetchWithRetry aborta quando a resposta pendura", async () => {
  // Rede que abre e nunca responde — o caso que deixava a UI em "Calculando..."
  // para sempre. `fetch` só rejeita quando o AbortController dispara.
  const original = globalThis.fetch;
  globalThis.fetch = ((_url: string, init?: RequestInit) =>
    new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new Error("AbortError")));
    })) as typeof fetch;

  const t0 = Date.now();
  await assert.rejects(() => fetchWithRetry("http://x", {}, 0, 1, 60));
  const decorrido = Date.now() - t0;

  globalThis.fetch = original;
  assert.ok(decorrido < 2000, `deveria abortar rápido, levou ${decorrido}ms`);
});

test("o teto de espera é explícito e finito", () => {
  assert.ok(Number.isFinite(FETCH_TIMEOUT_MS) && FETCH_TIMEOUT_MS > 0);
});
