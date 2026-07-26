import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { lintBlogFiscal, type ClassTribValid } from "./blogFiscalLint";

const here = dirname(fileURLToPath(import.meta.url)); // frontend/src/lib
// Fonte oficial vive no backend (monorepo); o checkout do CI traz tudo.
const CLASSTRIB = join(here, "..", "..", "..", "backend", "app", "data", "classtrib.json");
const BLOG_DIR = join(here, "..", "..", "content", "blog");

const data = JSON.parse(readFileSync(CLASSTRIB, "utf-8")) as {
  by_code: Record<string, unknown>;
  cst_descriptions: Record<string, unknown>;
};
const valid: ClassTribValid = {
  codes: new Set(Object.keys(data.by_code)),
  csts: new Set(Object.keys(data.cst_descriptions)),
};

test("blog: nenhum cClassTrib/CST fabricado nos posts (vs tabela oficial SVRS)", () => {
  const files = readdirSync(BLOG_DIR).filter((f) => f.endsWith(".mdx"));
  assert.ok(files.length > 0, "deve haver posts para validar");
  const problems: string[] = [];
  for (const f of files) {
    const mdx = readFileSync(join(BLOG_DIR, f), "utf-8");
    for (const finding of lintBlogFiscal(mdx, valid)) {
      problems.push(`${f}: [${finding.rule}] ${finding.message}`);
    }
  }
  assert.equal(problems.length, 0, `Conteúdo fiscal fabricado detectado:\n${problems.join("\n")}`);
});

test("guard: cClassTrib descrito como '8 dígitos' → erro", () => {
  const f = lintBlogFiscal("O cClassTrib tem 8 dígitos organizados em grupos.", valid);
  assert.ok(f.some((x) => x.rule === "CCLASSTRIB_DIGITOS"));
});

test("guard: cClassTrib '6 dígitos' → ok", () => {
  const f = lintBlogFiscal("O cClassTrib tem 6 dígitos.", valid);
  assert.equal(f.filter((x) => x.rule === "CCLASSTRIB_DIGITOS").length, 0);
});

test("guard: código cClassTrib inexistente (6 díg) → erro", () => {
  const f = lintBlogFiscal("Use o código `999999` no campo.", valid);
  assert.ok(f.some((x) => x.rule === "CCLASSTRIB_INEXISTENTE"));
});

test("guard: <cClassTrib> de 8 dígitos → erro", () => {
  const f = lintBlogFiscal("<cClassTrib>20003400</cClassTrib>", valid);
  assert.ok(f.some((x) => x.rule === "CCLASSTRIB_INEXISTENTE"));
});

test("guard: exemplo fabricado de 8 díg rotulado cClassTrib → erro", () => {
  const f = lintBlogFiscal("o cClassTrib `20003400` aponta o regime", valid);
  assert.ok(f.some((x) => x.rule === "CCLASSTRIB_INEXISTENTE"));
});

test("guard: NCM de 8 díg em backtick NÃO é confundido com cClassTrib", () => {
  const f = lintBlogFiscal("o NCM `30049099` é de medicamentos", valid);
  assert.equal(f.length, 0);
});

test("guard: CST inexistente (500) → erro", () => {
  const f = lintBlogFiscal("Itens imunes usam CST 500.", valid);
  assert.ok(f.some((x) => x.rule === "CST_INEXISTENTE"));
});

test("guard: conteúdo correto → sem findings", () => {
  const f = lintBlogFiscal(
    "O cClassTrib tem 6 dígitos. Ex.: `000001` (CST 000) e `200003` (CST 200).",
    valid,
  );
  assert.equal(f.length, 0);
});

test("guard: NT 2025.002 V1.36 citada (vigente é v1.40) → erro NT_VERSAO_DESATUALIZADA", () => {
  const f = lintBlogFiscal('instrumento: "NT 2025.002 V1.36"', valid);
  assert.ok(f.some((x) => x.rule === "NT_VERSAO_DESATUALIZADA"));
});

test("guard: NT 2025.002-RTC v1.40 citada (vigente) → sem finding", () => {
  const f = lintBlogFiscal('instrumento: "NT 2025.002-RTC v1.40"', valid);
  assert.equal(f.filter((x) => x.rule === "NT_VERSAO_DESATUALIZADA").length, 0);
});

test("guard: NT 2026.002 v1.00 citada (vigente) → sem finding", () => {
  const f = lintBlogFiscal("conforme a NT 2026.002 v1.00", valid);
  assert.equal(f.filter((x) => x.rule === "NT_VERSAO_DESATUALIZADA").length, 0);
});

test("guard: NT sem versão vigente registrada (ex. NT 007/2026) → sem finding (não derruba por falta de dado)", () => {
  const f = lintBlogFiscal("conforme a NT 999.999 v1.00", valid);
  assert.equal(f.filter((x) => x.rule === "NT_VERSAO_DESATUALIZADA").length, 0);
});
