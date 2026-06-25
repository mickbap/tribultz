/**
 * Corretor de conformidade do blog (#349) — modo CLI, para posts existentes.
 *
 *   npx tsx scripts/content-lint.ts          # checa e reporta (exit≠0 se houver auto-fix pendente)
 *   npx tsx scripts/content-lint.ts --fix     # aplica os auto-fixes nos arquivos
 *
 * Use no CI (sem --fix) como gate: falha se algum post tiver correção fiscal pendente.
 */
import fs from "node:fs";
import path from "node:path";
import { lintMdx } from "../src/lib/contentLint";

const CONTENT_DIR = path.join(process.cwd(), "content", "blog");
const FIX = process.argv.includes("--fix");

const files = fs.existsSync(CONTENT_DIR)
  ? fs.readdirSync(CONTENT_DIR).filter((f) => f.endsWith(".mdx"))
  : [];

let pendingFixes = 0;
let warns = 0;

for (const file of files) {
  const full = path.join(CONTENT_DIR, file);
  const original = fs.readFileSync(full, "utf-8");
  const { mdx, findings } = lintMdx(original);
  if (findings.length === 0) continue;

  console.log(`\n${file}`);
  for (const f of findings) {
    console.log(`  [${f.severity === "fix" ? "FIX" : "warn"}] ${f.rule}: ${f.message}`);
    if (f.severity === "fix") pendingFixes++;
    else warns++;
  }
  if (FIX && mdx !== original) {
    fs.writeFileSync(full, mdx, "utf-8");
    console.log("  → corrigido.");
  }
}

console.log(`\nResumo: ${files.length} posts | auto-fix ${FIX ? "aplicados" : "pendentes"}: ${pendingFixes} | warnings: ${warns}`);

// Sem --fix, falha se houver correção fiscal pendente (gate de CI). Warnings não bloqueiam.
if (!FIX && pendingFixes > 0) {
  console.error("\n✖ Há correções fiscais pendentes. Rode `npm run content:lint:fix` ou ajuste manualmente.");
  process.exit(1);
}
