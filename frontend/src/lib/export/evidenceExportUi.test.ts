import assert from "node:assert/strict";
import test from "node:test";
import { toastFromExportError } from "./evidenceExportUi";

test("toastFromExportError retorna info para placeholder de API indisponivel", () => {
  const feedback = toastFromExportError(new Error("Export via API ainda nao disponivel."));
  assert.equal(feedback.tone, "info");
  assert.equal(feedback.message, "Export via API ainda não disponível. Use Mock Mode ou tente novamente mais tarde.");
});

test("toastFromExportError retorna erro padrao para falha generica", () => {
  const feedback = toastFromExportError(new Error("API 500: boom"));
  assert.equal(feedback.tone, "error");
  assert.equal(feedback.message, "Falha ao exportar evidências: API 500: boom");
});
