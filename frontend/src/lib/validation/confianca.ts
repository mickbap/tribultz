/**
 * Limiares de confiança da classificação NCM/cClassTrib — fonte única (#660, L2.4).
 *
 * Os valores 70% e 85% já eram coerentes entre si; o problema apontado no
 * parecer era dispersão — viviam soltos em resposta de FAQ (`page.tsx:26,30,222`)
 * e no badge do widget (`Classifier.tsx:22-26`), cada um escrito à mão. Mudar a
 * régua exigia achar todos.
 *
 * Nenhuma superfície promete autorização automática, e nada aqui muda isso: a
 * régua é de *confiança da sugestão*, não de aprovação fiscal. A recomendação de
 * confirmar com o contador continua valendo em qualquer faixa.
 */

/** Acima disto, a sugestão tem alta probabilidade de acerto. */
export const CONFIANCA_ALTA = 0.85;

/** Abaixo disto, a sugestão deve ser confirmada com o contador antes de usar. */
export const CONFIANCA_MINIMA = 0.7;

export const CONFIANCA_ALTA_PCT = Math.round(CONFIANCA_ALTA * 100);
export const CONFIANCA_MINIMA_PCT = Math.round(CONFIANCA_MINIMA * 100);

export type FaixaConfianca = "alta" | "media" | "baixa";

export function faixaDeConfianca(valor: number): FaixaConfianca {
  if (valor >= CONFIANCA_ALTA) return "alta";
  if (valor >= CONFIANCA_MINIMA) return "media";
  return "baixa";
}

/** Régua visível ao usuário — mesma ordem em que aparece na página. */
export const REGUA_CONFIANCA: { faixa: FaixaConfianca; rotulo: string; acao: string }[] = [
  {
    faixa: "alta",
    rotulo: `${CONFIANCA_ALTA_PCT}% ou mais`,
    acao: "Alta probabilidade de acerto — ainda assim, valide com o contador antes de usar em produção.",
  },
  {
    faixa: "media",
    rotulo: `${CONFIANCA_MINIMA_PCT}% a ${CONFIANCA_ALTA_PCT - 1}%`,
    acao: "Sugestão plausível — confirme o enquadramento antes de emitir.",
  },
  {
    faixa: "baixa",
    rotulo: `abaixo de ${CONFIANCA_MINIMA_PCT}%`,
    acao: "Confirme com o contador. Casos críticos (regimes especiais, exportação) exigem revisão humana.",
  },
];
