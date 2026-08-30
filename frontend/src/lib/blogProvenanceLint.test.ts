/**
 * Dois gates independentes (ROUND BLOG 30/08-N).
 *
 * PUBLICATION_GATE responde "este conteúdo aprovado publica corretamente?".
 * PROVENANCE_AUDIT responde "já atingiu o padrão máximo de rastreabilidade?".
 * Só o primeiro bloqueia. O segundo é backlog.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { lintProvenance, isTechnical, bloqueiaPublicacao, dividaDeAuditoria, auditoriaPendente } from "./blogProvenanceLint";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const dir = join(raiz, "content", "blog");
const arquivos = readdirSync(dir).filter((f) => f.endsWith(".mdx"));
const mdx = (f: string) => readFileSync(join(dir, f), "utf8");

const PROV_OK = `provenance:
  - claim_scope: "Rejeição 1024 decorre da RV UB14-20"
    claim_classification: "FATO_NORMATIVO"
    artifact: "NT 2025.002-RTC"
    artifact_version: "1.51"
    rule_item: "UB14-20"
    source_authority: "Portal Nacional da NF-e"
    source_url: "https://www.nfe.fazenda.gov.br/portal/x"
    verified_at: "2026-08-30"
`;
const post = (extra: string, corpo = "<p>Rejeição 1024 e cClassTrib.</p>") =>
  `---\ntitle: "T"\nslug: "novo-artigo-tecnico"\n${extra}---\n${corpo}`;

test("PUBLICATION_GATE: nenhum artigo do blog está impedido de publicar", () => {
  for (const f of arquivos) {
    const r = bloqueiaPublicacao(lintProvenance(mdx(f)));
    assert.equal(r.length, 0, `${f}: ${r.map((x) => x.message).join(" | ")}`);
  }
});

test("fast lane: artigo aprovado sem provenance PUBLICA, com auditoria pendente", () => {
  // O caso que motivou o Round N: conteúdo liberado pelo Jurídico não pode
  // ficar preso porque falta metadata acessória.
  const r = lintProvenance(post(""));
  assert.equal(bloqueiaPublicacao(r).length, 0, "ausência de provenance não pode impedir publicação");
  assert.ok(dividaDeAuditoria(r).some((x) => x.rule === "PROVENANCE_AUSENTE"), "mas vira dívida registrada");
});

test("provenance declarada e malformada continua bloqueando", () => {
  // Aqui não é padrão de excelência: é bug. Bloco quebrado rende errado.
  const r = lintProvenance(post(PROV_OK.replace('    verified_at: "2026-08-30"\n', "")));
  assert.ok(bloqueiaPublicacao(r).length > 0, "provenance quebrada é erro de publicação");
});

test("PROVENANCE_AUDIT é relatório derivado, não lista curada", () => {
  const pend = auditoriaPendente(arquivos.map((f) => ({ slug: f.replace(".mdx", ""), mdx: mdx(f) })));
  // Hoje o acervo está completo; o valor do teste é o mecanismo continuar
  // derivando do conteúdo em vez de depender de alguém manter uma lista.
  assert.ok(Array.isArray(pend));
  assert.ok(pend.every((s) => arquivos.includes(`${s}.mdx`)));
});

test("artigo contido não é barrado — conter é urgente, corrigir é cuidadoso", () => {
  assert.equal(lintProvenance(post('noindex: true\nnoindexReason: "x"\n')).length, 0);
});

test("artigo não-técnico não exige provenance", () => {
  const s = `---\ntitle: "T"\nslug: "institucional"\n---\n<p>Texto sobre cultura da empresa.</p>`;
  assert.equal(isTechnical(s), false);
  assert.equal(lintProvenance(s).length, 0);
});

test("campo obrigatório ausente reprova", () => {
  for (const campo of ["claim_scope", "claim_classification", "artifact", "source_authority", "source_url", "verified_at"]) {
    // Substitui por campo neutro em vez de apagar a linha: apagar levaria
    // junto o marcador `- ` quando o campo é o primeiro do bloco, e o teste
    // passaria a medir o parser, não a regra.
    const rx = new RegExp(`(^|\\n)(\\s*(?:- )?)${campo}:[^\\n]*`, "m");
    const r = lintProvenance(post(PROV_OK.replace(rx, `$1$2x_neutro: "v"`)));
    assert.ok(
      r.some((x) => x.rule === "PROVENANCE_CAMPO_OBRIGATORIO" && x.message.includes(campo)),
      `remover ${campo} deveria reprovar`,
    );
  }
});

test("claim_scope genérico reprova — é a lista de fontes com outro nome", () => {
  for (const generico of ["o artigo", "todo o conteúdo", "geral", "todas as afirmações"]) {
    const r = lintProvenance(post(PROV_OK.replace(/claim_scope: ".*"/, `claim_scope: "${generico}"`)));
    assert.ok(r.some((x) => x.rule === "PROVENANCE_ESCOPO_GENERICO"), `"${generico}" deveria reprovar`);
  }
});

test("claim_classification fora do enum reprova", () => {
  const r = lintProvenance(post(PROV_OK.replace(/claim_classification: ".*"/, 'claim_classification: "PROVAVEL"')));
  assert.ok(r.some((x) => x.rule === "PROVENANCE_CLASSIFICACAO_INVALIDA"));
});

test("NAO_DETERMINADO é classificação legítima", () => {
  const r = lintProvenance(post(PROV_OK.replace(/claim_classification: ".*"/, 'claim_classification: "NAO_DETERMINADO"')));
  assert.equal(r.length, 0);
});

test("claim que cita regra sem rule_item reprova", () => {
  const semRule = PROV_OK.replace(/^\s*rule_item: .*$\n/m, "");
  assert.ok(lintProvenance(post(semRule)).some((x) => x.rule === "PROVENANCE_RULE_ITEM_AUSENTE"));
});

test("source_url e verified_at inválidos reprovam", () => {
  assert.ok(lintProvenance(post(PROV_OK.replace(/source_url: ".*"/, 'source_url: "portal-nfe"')))
    .some((x) => x.rule === "PROVENANCE_URL_INVALIDA"));
  assert.ok(lintProvenance(post(PROV_OK.replace(/verified_at: ".*"/, 'verified_at: "ontem"')))
    .some((x) => x.rule === "PROVENANCE_VERIFIED_AT_INVALIDO"));
});

test("frontmatter de todo post é YAML válido", () => {
  // Aspas internas não escapadas quebraram o parser durante este próprio round
  // e nenhum guard pegou: os testes liam o frontmatter por regex.
  for (const f of arquivos) {
    const fm = /^---\n([\s\S]*?)\n---/.exec(mdx(f));
    assert.ok(fm, `${f}: sem frontmatter`);
    for (const linha of fm![1].split("\n")) {
      const m = /^([a-zA-Z_]+):\s*"(.*)"\s*$/.exec(linha);
      if (m) assert.ok(!/(?<!\\)"/.test(m[2]), `${f}: aspa não escapada em ${m[1]}`);
    }
  }
});
