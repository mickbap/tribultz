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

/**
 * Versão vigente de cada Nota Técnica coberta pelo motor — fonte única pro
 * `blogFiscalLint` detectar posts do blog que citam uma versão desatualizada
 * (achado real: 4 posts citando "NT 2025.002 V1.36" quando a vigente já é
 * v1.40, 2026-07-26). Atualizar aqui sempre que o motor migrar pra versão
 * nova de uma NT — o lint aponta sozinho todo post que ficou pra trás.
 */
export const NT_CURRENT_VERSION: Record<string, string> = {
  "NT 2025.002": "1.40",
  "NT 2026.002": "1.00",
};

/**
 * NT 2025.002 v1.51 (04/08/2026) e NT 2026.002 v1.10 (04/08/2026) foram publicadas
 * mas NÃO disparam bump aqui — decisão deliberada, não esquecimento:
 * - v1.51 tem DUAS frentes (corrigido em 11/08/2026 — a redação anterior dizia que era
 *   "um patch pontual sobre UMA regra", o que é falso e fez o diff ser dispensado):
 *     (a) UB12-10/Rejeição 1115 — implementação em produção passou a "futura, sem data";
 *     (b) ~22 regras alteradas (B25-80, I08-140, I08-144, família UB13–UB131, VC02-14,
 *         VC02-30), homologação até 01/09/2026 e produção a partir de 05/10/2026.
 *   Do grupo (b) o motor implementa só VC02-14, já ajustada (ver DEVOLUCAO_DFEREF_DATE
 *   em xmlRules.ts). As demais não são cobertas — lacuna de cobertura, não regressão.
 *   O núcleo que os posts citam (CST, cClassTrib, CEST, totais W03) segue inalterado,
 *   e é por isso que o bump global continua indevido: marcaria ~13 posts hoje corretos
 *   como desatualizados (falso positivo em massa).
 * - v1.10 é um lote de regras novas/alteradas (homologação 01/09, produção 05/10)
 *   que o motor ainda não implementa; nosso core coberto (tpImp=6, 706/707/708/715,
 *   I08-150/725) é do lote v1.00 e continua correto citando v1.00.
 * O achado de v1.51 sobre a 1115 foi absorvido nos textos do motor (ver
 * `ibscbsGroupPresenceSev`/`IBSCBS_PRESENCA_SUSPENSA_NOTE` em xmlRules.ts, que já
 * citam v1.51 nesse ponto específico) e no updateNote dos posts afetados — não
 * por este bump global. Reavaliar se uma NT futura alterar mais do que uma regra
 * pontual, ou se o motor vier a implementar rules do lote v1.10.
 */
