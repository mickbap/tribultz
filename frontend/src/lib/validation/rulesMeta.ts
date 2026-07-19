/**
 * Número canônico de regras determinísticas do motor (RF-1 — SPEC site).
 *
 * Fonte única reutilizada por copy, blog e metadados (SEO/OG/Twitter), para que o
 * site nunca divirja do engine. Conta as regras de validação ATIVAS do
 * `xmlRules.ts`, excluindo os placeholders (lembretes que só emitem ALERT e não
 * validam nada). Hoje: 37 ruleIds distintos − 2 placeholders = 35.
 *
 * Anti-drift: `rulesMeta.test.ts` extrai os ruleIds reais do `xmlRules.ts` e falha
 * se esta contagem sair de sincronia com o engine. Ao adicionar/remover uma regra,
 * o teste aponta a atualização necessária aqui.
 */

/** ruleIds que NÃO contam como "regra de validação" (lembretes informativos ALERT). */
export const PLACEHOLDER_RULE_IDS: readonly string[] = ["BENEFITS_PLACEHOLDER", "NCM_PLACEHOLDER"];

/** Quantidade canônica de regras determinísticas ativas. */
export const RULES_COUNT = 35;

/**
 * Rótulo padrão ancorado à autoridade externa (a NT define o conjunto de regras).
 * A partir de #406, o engine cobre regras de Notas Técnicas distintas — NF-e/NFC-e
 * (NT 2025.002-RTC v1.40 + NT 2026.002 v1.00 — DANFE Simplificado Tipo 2, #405) e
 * NFS-e (NT 007/2026, SE/CGNFS-e) — por isso o rótulo cita todas em vez de uma só.
 */
export const RULES_LABEL = `${RULES_COUNT} regras determinísticas alinhadas às Notas Técnicas oficiais (NT 2025.002-RTC v1.40 + NT 2026.002 v1.00 — NF-e/NFC-e; NT 007/2026 — NFS-e)`;

/**
 * Quantidade de classificações cClassTrib carregadas da tabela oficial SVRS
 * (backend/app/data/classtrib.json, sincronizada na NT 2025.002-RTC v1.40 — #328).
 * Apresentar SEMPRE como escopo ("classificações mapeadas"), nunca como total/completo:
 * a tabela oficial cobre múltiplos DF-e; este é o conjunto carregado. Não derivado
 * automaticamente porque o arquivo-fonte vive no backend (fora do build do frontend).
 */
export const CLASSTRIB_COUNT = 164;
