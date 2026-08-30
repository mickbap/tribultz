/**
 * Gate de proveniência editorial (ROUND BLOG 30/08-C, Fase 3–4).
 *
 * O defeito que ele fecha: sete artigos P0 chegaram ao ar afirmando o que a
 * norma não diz, e nada no pipeline pediu que uma afirmação técnica apontasse
 * o artefato de onde veio. `legalRefs` existia, mas é bibliografia de rodapé —
 * não rastreia QUAL afirmação veio de ONDE, em QUE versão, conferida QUANDO.
 *
 * Escopo do gate, de propósito estreito:
 *
 * - vale para artigo **técnico** e **indexável**. Artigo contido (`noindex`)
 *   não é barrado: ele já está fora do índice, e exigir proveniência completa
 *   antes de permitir a contenção inverteria a ordem — conter é urgente,
 *   corrigir é cuidadoso.
 * - `claim_scope` pode cobrir um claim ou um grupo EXPLICITAMENTE delimitado.
 *   O que ele não pode é dizer "o artigo inteiro": isso é a lista genérica de
 *   fontes com outro nome.
 * - `NAO_DETERMINADO` é classificação legítima e não pode ser renderizada como
 *   afirmação factual — quem garante isso é o componente de UI, não este lint;
 *   aqui apenas exigimos que a classificação exista.
 */
export type ProvenanceFinding = { rule: string; severity: "error"; message: string };

/**
 * DÉBITO EDITORIAL DECLARADO — congelado em 2026-08-30.
 *
 * Artigos técnicos indexáveis que existiam ANTES do gate de proveniência.
 * Ligar o gate de uma vez sobre eles vermelharia o CI e bloquearia até as
 * correções P0 — inclusive as que este gate existe para proteger.
 *
 * A escolha aqui é tornar a dívida VISÍVEL e CONTÁVEL em vez de invisível: a
 * lista é uma catraca. Nenhum slug pode ser acrescentado (há teste que falha
 * se crescer), e cada correção editorial remove um. Artigo novo e artigo P0
 * corrigido cumprem o gate imediatamente, sem exceção.
 *
 * Não confundir com aprovação: estar aqui significa "ainda não auditado", não
 * "conteúdo verificado".
 */
export const DEBITO_PROVENANCE_2026_08_30: readonly string[] = [
  "api-validacao-xml-nfe-na-pratica",
  "como-calcular-aliquota-cbs-ibs",
  "como-prevenir-falhas-autorizadoras-emissao-fiscal",
  "como-revisar-catalogo-fiscal-ibs-cbs",
  "como-testar-campos-tributarios-antes-da-emissao",
  "erp-versus-inteligencia-tributaria",
  "evidencia-auditavel-reforma-tributaria",
  "exemplo-erro-cst-cclasstrib",
  "guia-campos-fiscais-nfe",
  "guia-rejeicoes-nt-2026-002-nf-e",
  "guia-sped-fiscal-reforma-tributaria",
  "guia-testes-cbs-ibs-2026",
  "guia-transicao-tributaria-operacional",
  "impacto-cbs-ibs-faturamento-operacao",
  "penalidades-cbs-ibs-2026",
  "por-que-nf-e-sofre-rejeicao",
  "principais-riscos-emissao-documentos-eletronicos",
  "qual-diferenca-entre-cbs-ibs",
  "quando-emitir-nota-com-ibs",
  "transicao-fiscal-2026-operacao-preparada",
  "validacao-deterministica-versus-conferencia-manual",
  "validacao-previa-ou-pos-emissao",
] as const;

const CLASSIFICACOES = ["FATO_NORMATIVO", "INTERPRETACAO_SEGURA", "NAO_DETERMINADO"];

/** Sinais de que o artigo faz afirmação técnica material. */
const SINAIS_TECNICOS: RegExp[] = [
  /\b[Rr]ejei[çc][ãa]o\s+\d{3,4}\b/,
  /\bcStat\b/i,
  /\bcClassTrib\b/i,
  /\bNCM\b/,
  /\bCST\b/,
  /\bCFOP\b/,
  /\bNT\s+\d{4}\.\d{3}/,
  /\bIN\s+RFB\b/,
  /\b[A-Z]{1,3}\d{2}[a-z]?-\d{2,3}\b/, // regra de validação: UB14-20, N12-110, W34-20
  /\d+[,.]\d+\s?%/,                    // alíquota
];

const ESCOPO_GENERICO = [
  /^o artigo/i, /^artigo inteiro/i, /^todo o (artigo|texto|conte[úu]do)/i,
  /^geral$/i, /^todas as afirma/i, /^conte[úu]do$/i,
];

function frontmatter(mdx: string): string {
  const m = /^---\n([\s\S]*?)\n---/.exec(mdx);
  return m ? m[1] : "";
}

function corpo(mdx: string): string {
  return mdx.replace(/^---\n[\s\S]*?\n---/, "");
}

/** O artigo faz afirmação técnica material? `technical:` explícito vence. */
export function isTechnical(mdx: string): boolean {
  const fm = frontmatter(mdx);
  if (/^technical:\s*true\s*$/m.test(fm)) return true;
  if (/^technical:\s*false\s*$/m.test(fm)) return false;
  const texto = corpo(mdx).replace(/<[^>]*>/g, " ");
  return SINAIS_TECNICOS.some((rx) => rx.test(texto));
}

/** Blocos de `provenance:` do frontmatter, cru. */
function blocosProvenance(fm: string): string[] {
  const i = fm.search(/^provenance:\s*$/m);
  if (i < 0) return [];
  const resto = fm.slice(i).split("\n").slice(1);
  const linhas: string[] = [];
  for (const l of resto) {
    if (/^\S/.test(l)) break; // saiu do bloco
    linhas.push(l);
  }
  return linhas
    .join("\n")
    .split(/^\s{2}-\s/m)
    .slice(1);
}

export function lintProvenance(mdx: string, slug?: string): ProvenanceFinding[] {
  const out: ProvenanceFinding[] = [];
  const fm = frontmatter(mdx);
  const contido = /^noindex:\s*true\s*$/m.test(fm);

  // Artigo contido não é barrado — conter é urgente, corrigir é cuidadoso.
  if (contido || !isTechnical(mdx)) return out;

  // Débito declarado: não bloqueia, mas também não some do radar.
  const alvo = slug ?? /^slug:\s*["']?([^"'\n]+)/m.exec(fm)?.[1]?.trim() ?? "";
  if (DEBITO_PROVENANCE_2026_08_30.includes(alvo)) return out;

  const blocos = blocosProvenance(fm);
  if (blocos.length === 0) {
    out.push({
      rule: "PROVENANCE_AUSENTE",
      severity: "error",
      message:
        "artigo técnico indexável sem `provenance` — toda afirmação material precisa apontar artefato, autoridade, URL e data de verificação.",
    });
    return out;
  }

  blocos.forEach((b, i) => {
    const campo = (nome: string) =>
      new RegExp(`(^|\\n)\\s*${nome}:\\s*["']?([^"'\\n]+)`).exec(b)?.[2]?.trim() ?? "";
    const ref = `provenance[${i}]`;

    for (const obrigatorio of ["claim_scope", "claim_classification", "artifact", "source_authority", "source_url", "verified_at"]) {
      if (!campo(obrigatorio)) {
        out.push({
          rule: "PROVENANCE_CAMPO_OBRIGATORIO",
          severity: "error",
          message: `${ref}: \`${obrigatorio}\` ausente.`,
        });
      }
    }

    const classificacao = campo("claim_classification");
    if (classificacao && !CLASSIFICACOES.includes(classificacao)) {
      out.push({
        rule: "PROVENANCE_CLASSIFICACAO_INVALIDA",
        severity: "error",
        message: `${ref}: claim_classification \`${classificacao}\` fora do enum (${CLASSIFICACOES.join(", ")}).`,
      });
    }

    const escopo = campo("claim_scope");
    if (escopo && ESCOPO_GENERICO.some((rx) => rx.test(escopo))) {
      out.push({
        rule: "PROVENANCE_ESCOPO_GENERICO",
        severity: "error",
        message: `${ref}: claim_scope "${escopo}" não delimita nada — proveniência por artigo é a lista de fontes com outro nome.`,
      });
    }

    const url = campo("source_url");
    if (url && !/^https?:\/\//.test(url)) {
      out.push({ rule: "PROVENANCE_URL_INVALIDA", severity: "error", message: `${ref}: source_url não é URL.` });
    }

    const verified = campo("verified_at");
    if (verified && Number.isNaN(new Date(verified).getTime())) {
      out.push({ rule: "PROVENANCE_VERIFIED_AT_INVALIDO", severity: "error", message: `${ref}: verified_at \`${verified}\` não é data.` });
    }

    // Claim que decorre de regra/dispositivo precisa nomear qual.
    if (/\b[A-Z]{1,3}\d{2}[a-z]?-\d{2,3}\b|\bart\.?\s*\d+/i.test(escopo) && !campo("rule_item")) {
      out.push({
        rule: "PROVENANCE_RULE_ITEM_AUSENTE",
        severity: "error",
        message: `${ref}: o claim cita regra ou dispositivo mas não declara \`rule_item\`.`,
      });
    }
  });

  return out;
}
