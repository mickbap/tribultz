/**
 * Guard dos exemplos de cClassTrib na superfície pública (#632, L1.2).
 *
 * A UI exibia cinco códigos inventados de 7 caracteres (`0010100`, `0020010`,
 * `0030005`, `2000340`) enquanto a copy ao lado dizia — corretamente — que o
 * cClassTrib tem 6 dígitos. Cliente que copiasse o exemplo parametrizava a NF-e
 * com código inexistente.
 *
 * Duas checagens:
 *   (A) todo código exportado por `classtribExamples.ts` existe em `by_code`;
 *   (B) nenhum código solto sobrevive na copy — varredura por literais numéricos
 *       próximos da palavra "cClassTrib", validados contra a tabela.
 *
 * (B) é ancorada na proximidade da palavra de propósito: CEST tem 7 dígitos e
 * NCM tem 8, e ambos aparecem legitimamente nas mesmas páginas — uma varredura
 * por "qualquer número de 6-7 dígitos" acusaria os dois.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { CLASSTRIB_EXEMPLOS_UI } from "./classtribExamples";

const here = dirname(fileURLToPath(import.meta.url)); // frontend/src/lib/validation
// Fonte oficial vive no backend (monorepo); o checkout do CI traz tudo.
const CLASSTRIB = join(here, "..", "..", "..", "..", "backend", "app", "data", "classtrib.json");

const data = JSON.parse(readFileSync(CLASSTRIB, "utf-8")) as {
  by_code: Record<string, unknown>;
};
const CODES = new Set(Object.keys(data.by_code));

/** O módulo de exemplos é a fonte — validado por (A), não varrido por (B). */
const SELF = join(here, "classtribExamples.ts");

const ROOTS = [join(here, "..", "..", "app"), join(here, "..", "..", "components")];

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

test("A) todo exemplo de cClassTrib da UI existe na tabela oficial SVRS", () => {
  assert.ok(CODES.size > 100, `tabela carregada (${CODES.size} códigos)`);
  for (const code of CLASSTRIB_EXEMPLOS_UI) {
    assert.match(code, /^\d{6}$/, `${code} deve ter exatamente 6 dígitos`);
    assert.ok(
      CODES.has(code),
      `cClassTrib ${code} não existe em by_code — exemplos devem sair DA tabela, nunca ser inventados`,
    );
  }
});

test("B) nenhum cClassTrib solto na copy pública fora da tabela", () => {
  // Literal numérico de 6+ dígitos a até 60 chars da palavra "cClassTrib",
  // em qualquer ordem (o código pode vir antes ou depois da menção).
  const patterns = [
    /cClassTrib[^.\n]{0,60}?\b(\d{6,8})\b/gi,
    /\b(\d{6,8})\b[^.\n]{0,60}?cClassTrib/gi,
  ];

  const offenders: string[] = [];
  for (const root of ROOTS) {
    for (const file of walk(root)) {
      if (file === SELF) continue;
      const raw = readFileSync(file, "utf-8");
      const rel = file.slice(file.indexOf("src/"));
      for (const rx of patterns) {
        for (const m of raw.matchAll(rx)) {
          const code = m[1];
          if (CODES.has(code)) continue;
          offenders.push(`${rel}: "${code}" — não existe em by_code`);
        }
      }
    }
  }

  assert.deepEqual(
    offenders,
    [],
    "cClassTrib citado na UI que não existe na tabela oficial:\n" +
      offenders.map((o) => `  • ${o}`).join("\n"),
  );
});
