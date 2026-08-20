/**
 * cClassTrib citados na copy pública — fonte única, verificada contra a tabela
 * oficial SVRS (#632, L1.2 do Lote 1).
 *
 * Antes, a UI exibia cinco exemplos **inventados** de 7 caracteres (`0010100`,
 * `0020010`, `0030005`, `2000340`) — nenhum existe em
 * `backend/app/data/classtrib.json`. A copy dizia corretamente "6 dígitos" e os
 * exemplos ao lado tinham 7, induzindo parametrização inválida na NF-e do
 * cliente (cClassTrib inexistente → Rejeição 1024 / família 1106).
 *
 * Todo código aqui é real e escolhido DENTRO de `by_code`, com semântica
 * coerente com a frase onde aparece. `classtribExamples.test.ts` falha se algum
 * deixar de existir na tabela — que é re-sincronizada diariamente com a SVRS —
 * e também se alguém voltar a escrever um código solto na copy.
 */

/** CST 000 · Tributação integral — "Situações tributadas integralmente pelo IBS e CBS." */
export const CLASSTRIB_TRIBUTACAO_INTEGRAL = "000001";

/** CST 011 · Alíquotas uniformes reduzidas (60%) — "Planos de assistência à saúde" (art. 237). */
export const CLASSTRIB_REDUZIDO_60 = "011002";

/**
 * CST 200 · Alíquota reduzida, redução de 100% — "Vendas de produtos destinados à
 * alimentação humana relacionados no Anexo I" (LC 214/2025). É a cesta básica.
 */
export const CLASSTRIB_CESTA_BASICA = "200003";

/** Todos os códigos citados na superfície pública — o teste valida um a um. */
export const CLASSTRIB_EXEMPLOS_UI = [
  CLASSTRIB_TRIBUTACAO_INTEGRAL,
  CLASSTRIB_REDUZIDO_60,
  CLASSTRIB_CESTA_BASICA,
] as const;
