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
 * antiga que a COBERTA pelo motor (`NT_IMPLEMENTED_VERSION`, rulesMeta.ts) — achado
 * real: 4 posts
 * citando "NT 2025.002 V1.36" quando a vigente já é v1.40 (2026-07-26). Esse é o
 * mecanismo de detecção da estratégia de atualização de posts do blog.
 *
 * Regras G/H (#580): o gate de revisão humana do Soro (marcador REVISAR +
 * frontmatter obrigatório) é hoje só convenção — nada barra o merge se for
 * pulado. O #580 mergeou com tags/legalRefs vazios e o marcador ainda no
 * corpo porque o PR foi aberto via GITHUB_TOKEN (não dispara checks
 * `pull_request`) e ninguém rodou build localmente antes de aprovar. Como
 * `contentLint.ts` não é escaneado contra `content/blog/*.mdx` em nenhum
 * teste (só `blogFiscalLint.test.ts` faz isso), essas regras vivem aqui —
 * é o único lugar onde "error" realmente derruba o `frontend-build`.
 *
 * Filosofia: somos uma empresa de validação determinística — dogfood no nosso conteúdo.
 */

import { NT_IMPLEMENTED_VERSION } from "./validation/rulesMeta";
import { parsePostDate } from "./formatPostDate";

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
  //    à coberta pelo motor (NT_IMPLEMENTED_VERSION — nunca a upstream: publicação
  //    lá fora não é prova de cobertura aqui). Cobre "NT 2025.002 V1.36" e "…v1.40".
  const ntVersionRx = /NT\s+(\d{4}\.\d{3})(?:-RTC)?\s+[vV](\d+)\.(\d+)/g;
  for (const m of mdx.matchAll(ntVersionRx)) {
    const ntId = m[1];
    const citedMajor = parseInt(m[2], 10);
    const citedMinor = parseInt(m[3], 10);
    const current = NT_IMPLEMENTED_VERSION[`NT ${ntId}`];
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

  // G) Marcador de revisão do Soro ainda presente no corpo — post nunca foi
  //    auditado por um humano antes do merge (achado real: #580).
  if (/Gerado pelo Soro — REVISAR antes do merge/.test(mdx)) {
    out.push({
      rule: "REVISAR_PENDENTE",
      severity: "error",
      message:
        "Marcador de revisão do Soro ainda presente — remover após auditar precisão fiscal, legalRefs, tags e category.",
    });
  }

  // H) Frontmatter incompleto (tags/legalRefs vazios) em post já mergeado —
  //    `contentLint.ts` já sinaliza isso como WARN, mas nenhum teste escaneia
  //    posts reais contra ele; aqui vira ERROR e realmente bloqueia o build.
  if (/legalRefs:\s*\[\s*\]/.test(mdx)) {
    out.push({
      rule: "LEGALREFS_VAZIO",
      severity: "error",
      message: "legalRefs vazio — adicionar base legal antes de publicar.",
    });
  }
  if (/tags:\s*\[\s*\]/.test(mdx)) {
    out.push({
      rule: "TAGS_VAZIO",
      severity: "error",
      message: "tags vazias — adicionar tags antes de publicar.",
    });
  }

  // I) `publishedAt` precisa ser parseável (#633). O blog exibia "Invalid Date"
  //    em 15 dos 19 posts porque o render concatenava "T00:00:00" numa data que
  //    já era ISO completo. O render foi corrigido, mas o gate existe para o
  //    outro lado do problema: um post cuja data não seja interpretável de forma
  //    alguma não pode entrar — a UI agora renderiza vazio, o que é silencioso.
  //    Só se aplica a documento COM frontmatter: as demais regras são checadas
  //    também contra fragmentos de prosa nos testes unitários, e exigir
  //    `publishedAt` de um fragmento seria escopo errado — a regra é sobre o
  //    frontmatter, então pressupõe que exista um.
  const temFrontmatter = /^---\s*$/m.test(mdx.split("\n").slice(0, 2).join("\n"));
  const pub = /^publishedAt:\s*["']?([^"'\n]+?)["']?\s*$/m.exec(mdx);
  if (!temFrontmatter) {
    // fragmento sem frontmatter — regra I não se aplica
  } else if (!pub) {
    out.push({
      rule: "PUBLISHEDAT_AUSENTE",
      severity: "error",
      message: "publishedAt ausente no frontmatter — sem data não há como datar o post.",
    });
  } else if (parsePostDate(pub[1]) === null) {
    out.push({
      rule: "PUBLISHEDAT_INVALIDO",
      severity: "error",
      message:
        `publishedAt \`${pub[1]}\` não é parseável — use YYYY-MM-DD ou ISO 8601 completo.`,
    });
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
