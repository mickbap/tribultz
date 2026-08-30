/**
 * Conformidade com o baseline editorial aprovado pelo Jurídico.
 *
 * O texto aprovado é insumo, não sugestão: TITLE, META_TITLE,
 * META_DESCRIPTION e LEAD precisam bater caractere a caractere com o que foi
 * liberado. Revisão humana de PR não detecta uma vírgula trocada num LEAD de
 * 400 caracteres; comparação mecânica detecta.
 *
 * `BASELINE_EDITORIAL` é preenchido quando o pacote chega. Enquanto um slug
 * não estiver aqui, ele simplesmente não é coberto — o comparador só se
 * pronuncia sobre o que lhe foi entregue, e nunca inventa o esperado.
 */

export type BaselineEditorial = {
  TITLE: string;
  META_TITLE?: string;
  META_DESCRIPTION: string;
  LEAD: string;
};

/**
 * Slugs cobertos pelo baseline aprovado, por round de origem.
 *
 * ROUND BLOG 30/08-H: seis slugs cobertos. Nunca preencher por memória, por
 * dedução a partir do publicado, nem por reconstrução — só a partir do texto
 * entregue pelo Jurídico.
 */
/** Pacote ROUND BLOG 30/08-H, recebido em 30/08/2026. Texto aprovado pelo
 *  Jurídico — qualquer divergência com o arquivo publicado é reprovação. */
export const BASELINE_EDITORIAL: Record<string, BaselineEditorial> = {
  "rejeicao-960-nf-e": {
    "TITLE": "Rejeição 960 NF-e/NFC-e: ICMS monofásico sobre combustíveis e regra N12-110",
    "META_TITLE": "Rejeição 960: ICMS monofásico de combustíveis",
    "META_DESCRIPTION": "Entenda quando ocorre a Rejeição 960 da NF-e/NFC-e, as condições da regra N12-110 e por que ela não é uma rejeição de cClassTrib.",
    "LEAD": "A Rejeição 960 não é uma regra de cClassTrib nem nasceu com a Reforma Tributária do Consumo. Ela pertence ao conjunto de validações do ICMS monofásico sobre combustíveis e está associada à RV N12-110, aplicável às NF-e e NFC-e dos modelos 55 e 65."
  },
  "rejeicao-1024-nfe-cbs-ibs-como-corrigir": {
    "TITLE": "Rejeição 1024 NF-e/NFC-e: cClassTrib incompatível com CST — regra UB14-20",
    "META_TITLE": "Rejeição 1024: cClassTrib incompatível com CST IBS/CBS",
    "META_DESCRIPTION": "Entenda a Rejeição 1024, a regra UB14-20 e como validar a compatibilidade entre CST e cClassTrib pela tabela oficial da RTC.",
    "LEAD": "A Rejeição 1024 ocorre quando o `cClassTrib` informado é incompatível com o CST de IBS/CBS utilizado no item, segundo a tabela oficial aplicável. Ela não deve ser confundida com rejeições por ausência de grupo, alíquota ou diferimento."
  },
  "classtrib-2026-mapear-ncm-regime-ibs-cbs": {
    "TITLE": "cClassTrib em 2026: como NCM, operação e requisitos legais orientam a classificação",
    "META_TITLE": "cClassTrib e NCM: por que a classificação depende da operação",
    "META_DESCRIPTION": "Entenda por que NCM não determina sozinho o cClassTrib e como operação, CST e requisitos legais orientam a análise das sugestões oficiais.",
    "LEAD": "O NCM pode ser um elemento relevante para identificar tratamentos tributários, mas não determina sozinho o cClassTrib. O próprio Portal da Conformidade Fácil apresenta resultados como sugestões e exige que os requisitos legais e as características da operação sejam avaliados antes da classificação."
  },
  "classtrib-2026-ncm-mapeamento-completo": {
    "TITLE": "cClassTrib e NCM: guia completo de sugestões, CST e validação da Rejeição 1024",
    "META_TITLE": "cClassTrib e NCM: CST, sugestões e Rejeição 1024",
    "META_DESCRIPTION": "Entenda a função de NCM, CST e cClassTrib, o limite das sugestões oficiais e como validar combinações sem criar um mapeamento tributário universal.",
    "LEAD": "NCM, CST e cClassTrib se relacionam, mas não formam um de-para universal. O NCM pode restringir hipóteses; a escolha do tratamento depende dos fatos e requisitos legais; e a compatibilidade entre CST e cClassTrib pode ser validada objetivamente contra a tabela oficial."
  },
  "como-classificar-ncm-corretamente-2026": {
    "TITLE": "Como classificar NCM corretamente: RGI, NESH e consulta à Receita Federal",
    "META_TITLE": "Como classificar NCM corretamente: RGI, NESH e Receita",
    "META_DESCRIPTION": "Aprenda o processo de classificação NCM com RGI, NESH e consulta formal à Receita, sem confundir classificação da mercadoria com cClassTrib.",
    "LEAD": "Classificar corretamente uma mercadoria na NCM exige conhecer suas características objetivas, aplicar as Regras Gerais para Interpretação do Sistema Harmonizado e consultar as fontes oficiais pertinentes. NCM não é sinônimo de cClassTrib, e uma classificação tributária da RTC não corrige uma NCM tecnicamente errada."
  },
  "como-calcular-aliquota-cbs-ibs": {
    "TITLE": "Como calcular CBS e IBS em 2026: alíquotas de 0,9% e 0,1% sem confundir estimativas futuras",
    "META_TITLE": "CBS 0,9% e IBS 0,1% em 2026: como calcular",
    "META_DESCRIPTION": "Veja as alíquotas legais de CBS e IBS em 2026, as regras especiais do período de teste e por que 26,5% não é uma alíquota futura já fixada.",
    "LEAD": "Para os fatos geradores de 2026, a LC nº 214 estabelece CBS de 0,9% e IBS de 0,1%, observadas as regras específicas da operação e do período de transição. Percentuais como 8,8%, 17,7% e 26,5% foram divulgados historicamente como estimativas e não devem ser tratados como alíquotas futuras legalmente fixadas."
  }
};

const NFC = (s: string) => s.normalize("NFC").trim();

function frontmatter(mdx: string): string {
  return /^---\n([\s\S]*?)\n---/.exec(mdx)?.[1] ?? "";
}

function campo(fm: string, nome: string): string | undefined {
  return /* eslint-disable-next-line */ new RegExp(`^${nome}:\\s*"([\\s\\S]*?)"\\s*$`, "m").exec(fm)?.[1];
}

/** Primeiro parágrafo do corpo — o LEAD. */
function lead(mdx: string): string {
  const corpo = mdx.replace(/^---\n[\s\S]*?\n---/, "").replace(/^\s*\{\/\*[\s\S]*?\*\/\}\s*/, "");
  return corpo.trim().split(/\n\s*\n/)[0] ?? "";
}

export type DivergenciaBaseline = { campo: string; esperado: string; encontrado: string };

/**
 * Compara o arquivo com o baseline aprovado. Devolve as divergências —
 * lista vazia significa aplicação literal.
 */
export function conferirBaseline(mdx: string, esperado: BaselineEditorial): DivergenciaBaseline[] {
  const fm = frontmatter(mdx);
  const out: DivergenciaBaseline[] = [];
  const par: Array<[string, string | undefined, string | undefined]> = [
    ["TITLE", esperado.TITLE, campo(fm, "title")],
    ["META_TITLE", esperado.META_TITLE, campo(fm, "metaTitle")],
    ["META_DESCRIPTION", esperado.META_DESCRIPTION, campo(fm, "description")],
    ["LEAD", esperado.LEAD, lead(mdx)],
  ];
  for (const [nome, esp, got] of par) {
    if (esp === undefined) continue; // campo não fornecido pelo baseline
    if (NFC(got ?? "") !== NFC(esp)) {
      out.push({ campo: nome, esperado: NFC(esp), encontrado: NFC(got ?? "") });
    }
  }
  return out;
}
