/**
 * Corretor de conformidade de conteúdo do blog (#349). Aplica, por CÓDIGO, os guardrails
 * fiscais que antes eram só checklist humano — auto-corrige o determinístico e sinaliza o
 * resto. Usado pelo pipeline do Soro (na geração) e pelo CLI `content:lint` (posts existentes).
 *
 * Filosofia: somos uma empresa de validação determinística — dogfood no nosso próprio conteúdo.
 * Auto-fix só em correções SEGURAS (anexar disclaimer); tom/afirmações ficam como WARN p/ humano.
 */

export type LintFinding = {
  rule: string;
  severity: "fix" | "warn";
  message: string;
};

export type LintResult = { mdx: string; findings: LintFinding[] };

// Alíquotas de referência plena (carga cheia) — 8,8% CBS / 17,7% IBS.
const PLENA_RX = /8[.,]8\s*%|17[.,]7\s*%/;
// Contexto que torna o uso da plena seguro. O sinal CONFIÁVEL é citar as alíquotas de
// TESTE de 2026 (0,9% / 0,1%) ou "fase de teste" — não basta dizer "referência"/"2026"
// genéricos (um artigo pode falar "alíquota de referência" sem esclarecer a fase).
const CONTEXT_RX = /fase de teste|0[.,]9\s*%|0[.,]1\s*%/i;

const VIGENCIA_NOTE =
  "<p><strong>Atenção à vigência:</strong> 8,8% (CBS) e 17,7% (IBS) são as alíquotas de " +
  "<strong>referência do regime pleno</strong> (carga cheia da Reforma). Na " +
  "<strong>fase de teste de 2026</strong>, a emissão usa alíquotas reduzidas — " +
  "<strong>CBS 0,9% e IBS 0,1%</strong>. Aplique o percentual do período correto.</p>";

// Linguagem de promessa/garantia — não auto-corrige (tom), só sinaliza.
const PROMISE_RX =
  /\b(garant\w+|100\s*%\s*de\s*conformidade|zero\s+rejei\w+|sem\s+multas?|isen[çc][ãa]o\s+garantida|elimina\s+(as\s+)?multas)\b/gi;

function splitFrontmatter(mdx: string): { front: string; body: string } {
  const m = mdx.match(/^(---\n[\s\S]*?\n---\n)([\s\S]*)$/);
  return m ? { front: m[1], body: m[2] } : { front: "", body: mdx };
}

/**
 * Aplica os guardrails ao MDX. Retorna o MDX corrigido (auto-fixes seguros) + os achados.
 * Idempotente: rodar de novo não duplica correções.
 */
export function lintMdx(mdx: string): LintResult {
  const { front, body } = splitFrontmatter(mdx);
  const findings: LintFinding[] = [];
  let fixedBody = body;

  // R1 — alíquota plena sem contexto de fase → AUTO-FIX (anexa nota de vigência).
  if (PLENA_RX.test(fixedBody) && !CONTEXT_RX.test(fixedBody)) {
    fixedBody = `${fixedBody.trimEnd()}\n\n${VIGENCIA_NOTE}\n`;
    findings.push({
      rule: "ALIQUOTA_PLENA_SEM_CONTEXTO",
      severity: "fix",
      message: "Alíquota plena (8,8/17,7) sem contexto de 2026 — nota de vigência inserida automaticamente.",
    });
  }

  // R2 — linguagem de promessa/garantia → WARN (revisão humana decide o tom).
  const promises = fixedBody.match(PROMISE_RX);
  if (promises) {
    const uniq = [...new Set(promises.map((p) => p.toLowerCase()))];
    findings.push({
      rule: "PROMESSA",
      severity: "warn",
      message: `Linguagem de promessa: "${uniq.join('", "')}". Suavizar (ex.: "reduz o risco").`,
    });
  }

  // R3 — frontmatter incompleto p/ publicação (base legal / tags) → WARN.
  if (/legalRefs:\s*\[\s*\]/.test(front)) {
    findings.push({ rule: "LEGALREFS_VAZIO", severity: "warn", message: "legalRefs vazio — adicionar base legal antes de publicar." });
  }
  if (/tags:\s*\[\s*\]/.test(front)) {
    findings.push({ rule: "TAGS_VAZIO", severity: "warn", message: "tags vazias — adicionar tags." });
  }

  return { mdx: front + fixedBody, findings };
}
