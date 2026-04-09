import assert from "node:assert/strict";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";

import { chromium } from "playwright";

const APP_BASE = process.env.CALCULADORA_E2E_BASE_URL ?? "http://127.0.0.1:3000";
const API_BASE = process.env.CALCULADORA_E2E_API_BASE
  ?? process.env.NEXT_PUBLIC_API_BASE_URL
  ?? "http://localhost:8000";

async function waitForHttp(url: string, timeoutMs = 60_000): Promise<void> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch {
      // Keep polling until the timeout expires.
    }
    await delay(500);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

test("calculadora smoke exposes 27 UFs and renders result card from browser flow", { timeout: 120_000 }, async (t) => {
  await waitForHttp(`${APP_BASE}/calculadora`);

  const browser = await chromium.launch({ headless: true });
  t.after(async () => {
    await browser.close();
  });

  const page = await browser.newPage();
  let capturedHeaders: Record<string, string> | null = null;
  let capturedBody: Record<string, unknown> | null = null;

  await page.route(`${API_BASE}/api/v1/public/calculadora/regime-geral`, async (route) => {
    const request = route.request();
    capturedHeaders = request.headers();
    capturedBody = request.postDataJSON() as Record<string, unknown>;

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        vBC: "1000.00",
        pCBS: "0.0880",
        vCBS: "88.00",
        pIBSUF: "0.1120",
        vIBSUF: "112.00",
        pIBSMun: "0.0650",
        vIBSMun: "65.00",
        vIBS: "177.00",
        total_tributos: "265.00",
        aliquota_efetiva: "0.2650",
        rate_source: "uf_default",
        cst: "000",
        cst_desc: "Tributacao normal (ad valorem)",
        xml_snippet: "<IBSCBS><CST>000</CST></IBSCBS>",
        data_policy: "Nenhum dado e armazenado.",
        upgrade_cta: "Crie sua conta gratuita.",
      }),
    });
  });

  await page.goto(`${APP_BASE}/calculadora`, { waitUntil: "networkidle" });

  const ufSelect = page.locator("select").first();
  const ufOptions = ufSelect.locator("option");
  assert.equal(await ufOptions.count(), 27);
  assert.equal(await ufOptions.nth(0).textContent(), "AC — Acre");
  assert.equal(await ufOptions.nth(26).textContent(), "TO — Tocantins");

  await ufSelect.selectOption("RS");
  await page.locator('input[type="number"]').first().fill("1000.00");
  await page.getByRole("button", { name: "Calcular CBS/IBS" }).click();

  await page.getByRole("heading", { name: "Resultado do Cálculo" }).waitFor();

  assert.ok(capturedHeaders, "calculator request was not captured");
  assert.ok(capturedBody, "calculator payload was not captured");
  assert.equal(capturedBody?.uf_destino, "RS");
  assert.equal(capturedBody?.base_value, "1000.00");
  assert.equal(capturedBody?.quantity, "1");
  assert.equal(capturedBody?.cst, "000");
  assert.ok(capturedHeaders?.["x-transaction-id"], "missing X-Transaction-Id header");

  const bodyText = await page.locator("body").innerText();
  assert.match(bodyText, /Resultado do Cálculo/u);
  assert.match(bodyText, /Alíquota efetiva/u);
  assert.match(bodyText, /Tx:/u);
  assert.match(bodyText, /XML <IBSCBS> — pronto para o ERP/u);
});
