/**
 * Guard determinístico anti-fabricação para o conteúdo do blog (follow-up do #349).
 *
 * O `contentLint` pega alíquota-plena-sem-contexto e linguagem de promessa, mas NÃO
 * pegava conteúdo técnico FABRICADO sobre o conceito-bandeira — ex.: cClassTrib
 * descrito como "8 dígitos" (o oficial tem 6), códigos inexistentes (`20003400`) e
 * CSTs inventados (500/610/700). Esse erro chegou a ser publicado (corrigido no #394).
 *
 * Este guard valida as afirmações sobre cClassTrib/CST de um post contra a TABELA
 * OFICIAL SVRS (`backend/app/data/classtrib.json`). Roda no CI via `blogFiscalLint.test.ts`
 * sobre todos os posts — determinístico, sem LLM, custo zero de token.
 *
 * Também valida (regra F) que nenhum post cita uma versão de Nota Técnica mais
 * antiga que a vigente (`NT_CURRENT_VERSION`, rulesMeta.ts) — achado real: 4 posts
 * citando "NT 2025.002 V1.36" quando a vigente já é v1.40 (2026-07-26). Esse é o
 * mecanismo de detecção da estratégia de atualização de posts do blog.
 *
 * Filosofia: somos uma empresa de validação determinística — dogfood no nosso conteúdo.
 */

import { NT_CURRENT_VERSION } from "./validation/rulesMeta";

export type FiscalFinding = { rule: string; severity: "error"; message: string };

/** Conjuntos válidos derivados de classtrib.json (codes = by_code; csts = cst_descriptions). */
export type ClassTribValid = { codes: Set<string>; csts: Set<string> };

export function lintBlogFiscal(mdx: string, valid: ClassTribValid): FiscalFinding[] {
  const out: FiscalFinding[] = [];

  // A) Afirmação de tamanho: "cClassTrib … N dígitos" / "N dígitos … cClassTrib".
  //    O cClassTrib oficial tem 6 dígitos (CST[3] + sequencial[3]). `[^.\n]` não cruza
  //    frase/linha, evitando capturar o "3 dígitos" que descreve só o CST.
  const digitRx = [
    /cClassTrib[^.\n]{0,45}?\b(\d{1,2})\s*d[íi]gitos/gi,
    /\b(\d{1,2})\s*d[íi]gitos[^.\n]{0,30}?cClassTrib/gi,
  ];
  for (const rx of digitRx) {
    for (const m of mdx.matchAll(rx)) {
      if (m[1] !== "6") {
        out.push({
          rule: "CCLASSTRIB_DIGITOS",
          severity: "error",
          message: `cClassTrib descrito como ${m[1]} dígitos — o oficial tem 6 (CST[3] + sequencial[3]).`,
        });
      }
    }
  }

  // B) Valores no XML <cClassTrib>…</cClassTrib> devem existir na tabela.
  for (const m of mdx.matchAll(/<cClassTrib>\s*([0-9]+)\s*<\/cClassTrib>/gi)) {
    if (!valid.codes.has(m[1])) out.push(codeFinding(m[1]));
  }

  // C) Token de exatamente 6 dígitos em backtick → tratado como cClassTrib; deve existir.
  for (const m of mdx.matchAll(/`([0-9]{6})`/g)) {
    if (!valid.codes.has(m[1])) out.push(codeFinding(m[1]));
  }

  // D) Token de 7–8 dígitos em backtick rotulado como cClassTrib (e não NCM) → inválido
  //    por tamanho (o oficial tem 6). Pega exemplos fabricados como `20003400`.
  for (const m of mdx.matchAll(/`([0-9]{7,8})`/g)) {
    const idx = m.index ?? 0;
    const ctx = mdx.slice(Math.max(0, idx - 45), idx + 45);
    if (/cClassTrib/i.test(ctx) && !/\bNCM\b/i.test(ctx)) out.push(codeFinding(m[1]));
  }

  // E) CST IBS/CBS de 3 dígitos citado ("CST 500", "CST `610`") deve constar no conjunto oficial.
  for (const m of mdx.matchAll(/\bCST\s*`?([0-9]{3})`?/gi)) {
    if (!valid.csts.has(m[1])) {
      out.push({
        rule: "CST_INEXISTENTE",
        severity: "error",
        message: `CST \`${m[1]}\` não consta na tabela oficial IBS/CBS (ex.: 000, 200, 400, 410, 510, 550, 620, 800).`,
      });
    }
  }

  // F) Versão de NT citada (legalRefs.instrumento ou prosa) desatualizada em relação
  //    à vigente (NT_CURRENT_VERSION). Cobre "NT 2025.002 V1.36" e "NT 2025.002-RTC v1.40".
  const ntVersionRx = /NT\s+(\d{4}\.\d{3})(?:-RTC)?\s+[vV](\d+)\.(\d+)/g;
  for (const m of mdx.matchAll(ntVersionRx)) {
    const ntId = m[1];
    const citedMajor = parseInt(m[2], 10);
    const citedMinor = parseInt(m[3], 10);
    const current = NT_CURRENT_VERSION[`NT ${ntId}`];
    if (!current) continue;
    const [curMajor, curMinor] = current.split(".").map((n) => parseInt(n, 10));
    const isOlder = citedMajor !== curMajor ? citedMajor < curMajor : citedMinor < curMinor;
    if (isOlder) {
      out.push({
        rule: "NT_VERSAO_DESATUALIZADA",
        severity: "error",
        message: `Cita NT ${ntId} v${m[2]}.${m[3]} — a versão vigente é v${current}. Revisar conteúdo e atualizar legalRefs + updatedAt.`,
      });
    }
  }

  return out;
}

function codeFinding(code: string): FiscalFinding {
  const why =
    code.length !== 6
      ? `tem ${code.length} dígitos — o oficial tem 6`
      : "não existe na tabela oficial SVRS";
  return { rule: "CCLASSTRIB_INEXISTENTE", severity: "error", message: `cClassTrib \`${code}\` ${why}.` };
}
