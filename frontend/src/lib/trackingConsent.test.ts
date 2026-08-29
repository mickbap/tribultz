/**
 * Guard: nenhum rastreador de terceiro fora do portão de consentimento.
 *
 * O defeito que originou este teste: `layout.tsx` carregava o loader do
 * HubSpot (`//js.hs-scripts.com/49735644.js`) com `strategy="afterInteractive"`
 * de forma INCONDICIONAL, enquanto o GA4 — logo abaixo, no mesmo arquivo —
 * estava sob Consent Mode v2 com tudo `denied` por padrão. Na prática o
 * HubSpot deixava cookie em todo visitante sem consentimento, contrariando o
 * Guia Orientativo da ANPD que o resto do arquivo respeita.
 *
 * O HubSpot foi descomissionado do frontend (ROUND 18-A). O guard é de
 * texto-fonte de propósito: o que importa é que nenhum host de rastreio
 * reapareça no layout nem volte a ser permitido pela CSP.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const aqui = dirname(fileURLToPath(import.meta.url));
const layout = readFileSync(join(aqui, "..", "app", "layout.tsx"), "utf8");
const nextConfig = readFileSync(join(aqui, "..", "..", "next.config.ts"), "utf8");

const HOSTS_HUBSPOT = [
  "hs-scripts",
  "hs-analytics",
  "hs-banner",
  "hsadspixel",
  "usemessages",
  "hsforms",
  "hubspot.com",
  "hubapi.com",
];

test("layout não carrega nenhum script do HubSpot", () => {
  for (const host of HOSTS_HUBSPOT) {
    assert.ok(
      !layout.includes(host),
      `layout.tsx voltou a referenciar ${host} — rastreador de terceiro fora do consentimento`,
    );
  }
  assert.ok(
    !layout.includes("hs-script-loader"),
    "o loader do HubSpot voltou ao layout",
  );
});

test("CSP não permite nenhum host do HubSpot", () => {
  for (const host of HOSTS_HUBSPOT) {
    assert.ok(
      !nextConfig.includes(host),
      `next.config.ts voltou a permitir ${host} na CSP sem consumidor no frontend`,
    );
  }
});

test("o consentimento do GA continua negado por padrão", () => {
  // Esta remoção não pode afrouxar o que já estava correto.
  for (const chave of ["ad_storage", "ad_user_data", "ad_personalization", "analytics_storage"]) {
    assert.ok(
      new RegExp(`${chave}:\\s*'denied'`).test(layout),
      `${chave} deixou de ser 'denied' por padrão no layout`,
    );
  }
});
