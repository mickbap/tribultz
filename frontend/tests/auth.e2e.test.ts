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

test("auth guard redirects unauthenticated users from protected route to /login", { timeout: 60_000 }, async (t) => {
  await waitForHttp(`${APP_BASE}/login`);

  const browser = await chromium.launch({ headless: true });
  t.after(async () => {
    await browser.close();
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(`${APP_BASE}/jobs`, { waitUntil: "domcontentloaded" });

  await page.waitForURL(/\/login\?redirect=/, { timeout: 15_000 });

  const url = new URL(page.url());
  assert.equal(url.pathname, "/login");
  assert.equal(url.searchParams.get("redirect"), "/jobs");

  await page.getByRole("heading", { name: "Entrar" }).waitFor();
});

test("seeded JWT token bypasses auth guard and loads protected route", { timeout: 60_000 }, async (t) => {
  await waitForHttp(`${APP_BASE}/login`);

  const browser = await chromium.launch({ headless: true });
  t.after(async () => {
    await browser.close();
  });

  const context = await browser.newContext();
  await context.addInitScript(() => {
    window.localStorage.setItem("tribultz.token", "test-jwt-token");
    window.localStorage.setItem("tribultz.tenant", "00000000-0000-0000-0000-000000000001");
    window.localStorage.setItem("tribultz.account_type", "empresa");
  });
  const page = await context.newPage();

  await page.route("**/api/v1/jobs", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await page.goto(`${APP_BASE}/jobs`, { waitUntil: "networkidle" });

  // Expect to stay on /jobs (no redirect to /login)
  const url = new URL(page.url());
  assert.equal(url.pathname, "/jobs", `expected /jobs, got ${url.pathname}${url.search}`);
  await page.getByRole("heading", { name: /Jobs/ }).waitFor({ timeout: 10_000 });
});
