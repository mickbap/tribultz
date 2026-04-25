import assert from "node:assert/strict";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";

import { chromium } from "playwright";

const APP_BASE = process.env.CALCULADORA_E2E_BASE_URL ?? "http://127.0.0.1:3000";

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

const SAMPLE_XML = `<nfeProc><NFe><infNFe><det><imposto><IBSCBS><CST>000</CST></IBSCBS></imposto></det></infNFe></NFe></nfeProc>`;

const MOCK_JOB_ID = "00000000-0000-4000-8000-000000000001";
const MOCK_AUDIT_ID = "00000000-0000-4000-8000-000000000002";
const MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000001";

const MOCK_VALIDATION_RESPONSE = {
  job: {
    id: MOCK_JOB_ID,
    created_at: "2026-04-16T00:00:00Z",
    tenant_id: MOCK_TENANT_ID,
    transaction_id: "tx-test-001",
  },
  audit: {
    id: MOCK_AUDIT_ID,
    job_id: MOCK_JOB_ID,
    events: [],
  },
  findings: [
    {
      id: "finding-1",
      severity: "FATAL",
      rule_id: "CST_VALID",
      title: "CST inválido no grupo IBSCBS",
      where: {
        field: "CST",
        xpath: "//IBSCBS/CST",
        snippet: "<CST>000</CST>",
      },
      recommendation: "Revisar a tabela de CST conforme NT 2025.002-RTC.",
      evidence_ids: ["ev-1"],
    },
  ],
  evidences: [
    {
      id: "ev-1",
      type: "xml",
      label: "Trecho IBSCBS",
      xpath: "//IBSCBS",
      snippet: "<IBSCBS><CST>000</CST></IBSCBS>",
    },
  ],
  transaction_id: "tx-test-001",
};

const MOCK_JOB_DETAIL = {
  id: MOCK_JOB_ID,
  tenant_id: MOCK_TENANT_ID,
  status: "DONE",
  created_at: "2026-04-16T00:00:00Z",
  updated_at: "2026-04-16T00:00:01Z",
};

test("validate-xml flow: paste XML, submit, render findings and evidence", { timeout: 90_000 }, async (t) => {
  await waitForHttp(`${APP_BASE}/login`);

  const browser = await chromium.launch({ headless: true });
  t.after(async () => {
    await browser.close();
  });

  const context = await browser.newContext();
  await context.addInitScript((tenantId) => {
    window.localStorage.setItem("tribultz.token", "test-jwt-token");
    window.localStorage.setItem("tribultz.tenant", tenantId);
    window.localStorage.setItem("tribultz.account_type", "empresa");
  }, MOCK_TENANT_ID);

  const page = await context.newPage();

  let capturedHeaders: Record<string, string> | null = null;
  let capturedDocumentType: string | null = null;

  await page.route("**/api/v1/validate/xml", async (route) => {
    const request = route.request();
    capturedHeaders = request.headers();
    // FormData arrives as multipart; capture document_type from the raw body
    const postData = request.postData() ?? "";
    const match = postData.match(/name="document_type"\r?\n\r?\n([^\r\n]+)/);
    if (match) {
      capturedDocumentType = match[1];
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_VALIDATION_RESPONSE),
    });
  });

  await page.route(`**/api/v1/jobs/${MOCK_JOB_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_JOB_DETAIL),
    });
  });

  await page.goto(`${APP_BASE}/validate-xml`, { waitUntil: "networkidle" });

  await page.getByRole("heading", { name: "Validar XML" }).waitFor();

  await page.locator("select").first().selectOption("NFE");
  await page.locator("textarea").first().fill(SAMPLE_XML);

  await page.getByRole("button", { name: "Validar" }).click();

  await page.getByRole("heading", { name: "CST inválido no grupo IBSCBS" }).waitFor({ timeout: 15_000 });

  assert.ok(capturedHeaders, "validate/xml request was not captured");
  assert.equal(capturedHeaders?.authorization, "Bearer test-jwt-token");
  assert.equal(capturedHeaders?.["x-tenant-id"], MOCK_TENANT_ID);
  assert.ok(capturedHeaders?.["x-transaction-id"], "missing X-Transaction-Id header");
  assert.equal(capturedDocumentType, "NFE");

  const bodyText = await page.locator("body").innerText();
  assert.match(bodyText, /Bloqueio visual ativo: 1 finding\(s\) FATAL/u);
  assert.match(bodyText, /CST_VALID/u);
  assert.match(bodyText, new RegExp(MOCK_JOB_ID, "u"));
  assert.match(bodyText, /Trecho IBSCBS/u);
  assert.match(bodyText, /Revisar a tabela de CST/u);
});
