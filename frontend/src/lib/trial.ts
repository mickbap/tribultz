/**
 * Trial — verdade contratual única para a copy pública (#635, L1.5).
 *
 * Decisão de Produto de 16/08/2026. Antes havia TRÊS verdades simultâneas:
 *
 *   /register  "Grátis por 3 dias · 5 validações · Download TXT · Sem suporte"
 *   /pricing   "5 validações XML POR MÊS"
 *   home       "5 validações grátis" (sem prazo)
 *
 * A franquia é do trial INTEIRO, não mensal — `quota_period = trial_lifetime`.
 * Essa palavra tem consequência de código, não só de copy: o backend contava
 * por mês-calendário, então um trial ativado no dia 30 ganhava franquia nova no
 * dia 1º.
 *
 * Espelha `backend/app/data/trial_policy.json`, que é a fonte canônica servida
 * ao backend. `trial.test.ts` falha se os dois divergirem, e varre as
 * superfícies públicas atrás de número ou prazo de trial escrito à mão.
 */

export const TRIAL_DURATION_DAYS = 3;
export const TRIAL_VALIDATION_QUOTA = 5;

/** A franquia vale para o trial inteiro — não se renova por mês. */
export const TRIAL_QUOTA_PERIOD = "trial_lifetime" as const;

export const TRIAL_FEATURES = {
  txt: true,
  pdf: false,
  api: false,
  dashboard: false,
  technicalSupport: false,
} as const;

/** "Grátis por 3 dias" */
export const TRIAL_DURATION_LABEL = `Grátis por ${TRIAL_DURATION_DAYS} dias`;

/** "5 validações no período" — o sufixo evita a leitura de "por mês". */
export const TRIAL_QUOTA_LABEL = `${TRIAL_VALIDATION_QUOTA} validações no período`;

/** Linha completa para tabelas de plano. */
export const TRIAL_SUMMARY = `${TRIAL_DURATION_LABEL} · ${TRIAL_QUOTA_LABEL}`;

/** Itens do Trial em tabela de planos, derivados da política (nunca escritos à mão). */
export const TRIAL_FEATURE_LIST: string[] = [
  TRIAL_QUOTA_LABEL,
  "Download TXT",
  "Sem relatório PDF",
  "Sem dashboard",
  "Sem acesso à API",
  "Sem suporte técnico",
];
