/**
 * O comparador de baseline precisa provar que morde ANTES de existir baseline
 * preenchido — senão vira decoração que só será exercitada no dia em que o
 * pacote chegar, justamente quando não pode falhar.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { BASELINE_EDITORIAL, conferirBaseline, type BaselineEditorial } from "./blogBaseline";

const dir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "content", "blog");

const MDX = `---
title: "Título aprovado"
metaTitle: "Meta aprovado"
description: "Descrição aprovada."
slug: "x"
---

Lead aprovado do artigo.

Segundo parágrafo, que não é o lead.
`;
const OK: BaselineEditorial = {
  TITLE: "Título aprovado",
  META_TITLE: "Meta aprovado",
  META_DESCRIPTION: "Descrição aprovada.",
  LEAD: "Lead aprovado do artigo.",
};

test("baseline: aplicação literal não acusa divergência", () => {
  assert.deepEqual(conferirBaseline(MDX, OK), []);
});

test("baseline: cada campo trocado é acusado individualmente", () => {
  for (const campo of ["TITLE", "META_TITLE", "META_DESCRIPTION", "LEAD"] as const) {
    const adulterado = { ...OK, [campo]: OK[campo] + " (reescrito pelo Techlead)" };
    const d = conferirBaseline(MDX, adulterado);
    assert.equal(d.length, 1, `${campo}: divergência não detectada`);
    assert.equal(d[0].campo, campo);
  }
});

test("baseline: diferença sutil — vírgula, acento, espaço — também é divergência", () => {
  for (const lead of [
    "Lead aprovado do artigo",           // ponto final removido
    "Lead aprovado do artigo..",         // pontuação alterada
    "Lead aprovado  do artigo.",         // espaço duplo
    "Lead aprovada do artigo.",          // uma letra
  ]) {
    assert.equal(conferirBaseline(MDX, { ...OK, LEAD: lead }).length, 1, `passou: "${lead}"`);
  }
});

test("baseline: campo não fornecido pelo Jurídico não é cobrado", () => {
  const semMeta: BaselineEditorial = { ...OK, META_TITLE: undefined };
  assert.deepEqual(conferirBaseline(MDX.replace(/^metaTitle:.*\n/m, ""), semMeta), []);
});

test("baseline: todo slug coberto bate literalmente com o arquivo publicado", () => {
  for (const [slug, esperado] of Object.entries(BASELINE_EDITORIAL)) {
    const d = conferirBaseline(readFileSync(join(dir, `${slug}.mdx`), "utf8"), esperado);
    assert.deepEqual(
      d, [],
      `${slug}: ${d.map((x) => `${x.campo}\n  esperado: ${x.esperado}\n  arquivo:  ${x.encontrado}`).join("\n")}`,
    );
  }
});
