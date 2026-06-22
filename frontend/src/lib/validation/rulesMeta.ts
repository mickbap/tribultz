/**
 * Número canônico de regras determinísticas do motor (RF-1 — SPEC site).
 *
 * Fonte única reutilizada por copy, blog e metadados (SEO/OG/Twitter), para que o
 * site nunca divirja do engine. Conta as regras de validação ATIVAS do
 * `xmlRules.ts`, excluindo os placeholders (lembretes que só emitem ALERT e não
 * validam nada). Hoje: 22 ruleIds distintos − 2 placeholders = 20.
 *
 * Anti-drift: `rulesMeta.test.ts` extrai os ruleIds reais do `xmlRules.ts` e falha
 * se esta contagem sair de sincronia com o engine. Ao adicionar/remover uma regra,
 * o teste aponta a atualização necessária aqui.
 */

/** ruleIds que NÃO contam como "regra de validação" (lembretes informativos ALERT). */
export const PLACEHOLDER_RULE_IDS: readonly string[] = ["BENEFITS_PLACEHOLDER", "NCM_PLACEHOLDER"];

/** Quantidade canônica de regras determinísticas ativas. */
export const RULES_COUNT = 20;

/** Rótulo padrão ancorado à autoridade externa (a NT define o conjunto de regras). */
export const RULES_LABEL = `${RULES_COUNT} regras determinísticas alinhadas à NT 2025.002-RTC v1.40`;

/**
 * Quantidade de classificações cClassTrib carregadas da tabela oficial SVRS
 * (backend/app/data/classtrib.json, sincronizada na NT 2025.002-RTC v1.40 — #328).
 * Apresentar SEMPRE como escopo ("classificações mapeadas"), nunca como total/completo:
 * a tabela oficial cobre múltiplos DF-e; este é o conjunto carregado. Não derivado
 * automaticamente porque o arquivo-fonte vive no backend (fora do build do frontend).
 */
export const CLASSTRIB_COUNT = 156;
