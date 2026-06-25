import test from "node:test";
import assert from "node:assert/strict";
import { lintMdx } from "./contentLint";

const FM = '---\ntitle: "X"\nlegalRefs: []\ntags: []\n---\n';

test("#349 lint: alíquota plena SEM contexto → auto-fix (nota de vigência)", () => {
  const { mdx, findings } = lintMdx(`${FM}<p>Sujeita a 8,8% de CBS e 17,7% de IBS.</p>`);
  assert.ok(mdx.includes("CBS 0,9% e IBS 0,1%"), "nota de vigência inserida");
  assert.ok(findings.some((f) => f.rule === "ALIQUOTA_PLENA_SEM_CONTEXTO" && f.severity === "fix"));
});

test("#349 lint: alíquota plena COM contexto → não duplica", () => {
  const body = "<p>8,8% e 17,7% são a referência do regime pleno; em 2026 usa-se 0,9% e 0,1%.</p>";
  const { mdx, findings } = lintMdx(`${FM}${body}`);
  assert.ok(!findings.some((f) => f.rule === "ALIQUOTA_PLENA_SEM_CONTEXTO"));
  // idempotência: o corpo não ganha uma segunda nota
  assert.equal((mdx.match(/Aplique o percentual do período correto/g) ?? []).length, 0);
});

test("#349 lint: idempotente (rodar 2x não muda)", () => {
  const first = lintMdx(`${FM}<p>8,8% de CBS.</p>`).mdx;
  const second = lintMdx(first).mdx;
  assert.equal(first, second);
});

test("#349 lint: linguagem de promessa → warn", () => {
  const { findings } = lintMdx(`${FM}<p>Garante zero rejeição e elimina multas.</p>`);
  assert.ok(findings.some((f) => f.rule === "PROMESSA" && f.severity === "warn"));
});

test("#349 lint: frontmatter incompleto (legalRefs/tags vazios) → warn", () => {
  const { findings } = lintMdx(`${FM}<p>texto neutro</p>`);
  assert.ok(findings.some((f) => f.rule === "LEGALREFS_VAZIO"));
  assert.ok(findings.some((f) => f.rule === "TAGS_VAZIO"));
});
