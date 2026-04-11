/**
 * Mapa estático de justificativas técnicas por rule_id.
 *
 * Cada entrada descreve:
 * - base_legal: artigo(s) da LC 214/2025 ou LC 227/2024 aplicáveis
 * - explicacao: por que a regra existe e o que ela verifica
 * - correcao: o que o motor fez (ou recomenda) para sanar a não-conformidade
 *
 * Disponível apenas para planos Profissional, Empresarial e Contador.
 */

export type FiscalJustification = {
  base_legal: string;
  explicacao: string;
  correcao: string;
};

export const FISCAL_JUSTIFICATIONS: Record<string, FiscalJustification> = {
  XML_PARSE: {
    base_legal: "NT 2025.002-RTC – Nota Técnica de Requisitos de Transmissão de NF-e/NFS-e",
    explicacao:
      "O arquivo XML enviado não pôde ser interpretado pelo motor de validação. " +
      "A malformação estrutural impede qualquer análise fiscal subsequente, " +
      "tornando o documento inapto para transmissão ao SPED ou Nota Nacional.",
    correcao:
      "Reenvie o XML após correção da estrutura. Utilize um validador de schema XSD " +
      "compatível com a versão do layout declarada no atributo verProc.",
  },

  CST_3_DIGITS: {
    base_legal: "LC 214/2025, Art. 9º e Anexo I — Tabela de CST IBS/CBS; NT 2025.002-RTC, Leiaute v1.0",
    explicacao:
      "O Código de Situação Tributária (CST) do IBS/CBS deve ser informado com exatamente 3 dígitos " +
      "(ex: '000', '070', '410'). Valores com menos ou mais dígitos indicam migração incorreta " +
      "de tabelas antigas de PIS/COFINS ou ICMS, que usavam 2 dígitos.",
    correcao:
      "Corrija o campo <CST> no grupo gIBSCBS de cada item para o código de 3 dígitos " +
      "correspondente ao regime tributário do produto/serviço conforme Tabela CST IBS/CBS.",
  },

  CCLASSTRIB_6_DIGITS: {
    base_legal: "NT 2025.002-RTC, Leiaute v1.0, campo cClassTrib; Portaria SVRS sobre ClassTrib",
    explicacao:
      "O campo cClassTrib (Classificação Tributária) deve conter exatamente 6 dígitos numéricos " +
      "conforme tabela SVRS. Esse campo determina o regime de tributação monofásico, " +
      "imune ou reduzido do produto e é obrigatório para apuração correta de IBS/CBS.",
    correcao:
      "Consulte a tabela ClassTrib em https://cff.svrs.rs.gov.br/api/v1/consultas/classTrib " +
      "e preencha o campo cClassTrib com o código de 6 dígitos correspondente ao NCM do produto.",
  },

  SERVICE_CODE_6_DIGITS: {
    base_legal: "LC 214/2025, Art. 14 — Regras para NFS-e e ISS; NT 2025.002-RTC",
    explicacao:
      "Para documentos de serviço (NFS-e), o código de serviço municipal deve ter 6 dígitos " +
      "no formato definido pela Lista de Serviços (LC 116/2003 atualizada). Códigos truncados " +
      "ou com formatação livre impedem o correto enquadramento da alíquota IBS municipal.",
    correcao:
      "Ajuste o código de serviço para o formato de 6 dígitos definido pela tabela municipal " +
      "correspondente ao CNPJ emitente. Consulte a prefeitura do município de emissão.",
  },

  NCM_PLACEHOLDER: {
    base_legal: "LC 214/2025, Art. 9º, §2º — NCM obrigatório para NF-e de bens; TIPI/TBEPC",
    explicacao:
      "O campo NCM (Nomenclatura Comum do Mercosul) está preenchido com valor de teste " +
      "ou placeholder (00000000, 99999999 ou equivalente). O NCM real é obrigatório para " +
      "determinar a alíquota diferenciada ou a redução de base de cálculo aplicável ao produto.",
    correcao:
      "Substitua o NCM placeholder pelo código NCM real do produto conforme TIPI " +
      "(Tabela de Incidência do IPI) ou TBEPC (Tabela de Benefícios Específicos por Produto e Contribuinte).",
  },

  IBSCBS_MISSING: {
    base_legal:
      "LC 214/2025, Art. 9º, caput e §1º — Obrigatoriedade do grupo IBS/CBS na NF-e/NFS-e; " +
      "NT 2025.002-RTC, Leiaute v1.0, grupo gIBSCBS",
    explicacao:
      "A partir da vigência da LC 214/2025, toda NF-e de bens e NFS-e de serviços sujeitos " +
      "ao IBS/CBS deve incluir o grupo fiscal gIBSCBS com os campos pCBS, vCBS, pIBSUF, " +
      "vIBSUF, pIBSMun e vIBSMun. A ausência desse grupo configura omissão fiscal.",
    correcao:
      "Inclua o grupo <gIBSCBS> em cada item da nota com os valores de CBS e IBS " +
      "calculados conforme alíquotas da UF de destino. Use a Calculadora CBS/IBS " +
      "disponível em tribultz.com.br/calculadora.",
  },

  IBSCBS_CALC: {
    base_legal:
      "LC 214/2025, Art. 11 — Cálculo do CBS; Art. 23 — Cálculo do IBS; " +
      "NT 2025.002-RTC, Regra de Cálculo: vCBS = vBC × pCBS",
    explicacao:
      "O valor de CBS declarado (vCBS) diverge do valor calculado pelo motor " +
      "com base na alíquota (pCBS) aplicada sobre a base de cálculo (vBC). " +
      "Diferenças acima da tolerância de R$ 0,01 por item indicam erro de arredondamento " +
      "ou uso de alíquota incorreta.",
    correcao:
      "Recalcule vCBS = vBC × pCBS com arredondamento para 2 casas decimais (ABNT NBR 5891). " +
      "Verifique se pCBS é a alíquota federal vigente para o período de competência da nota.",
  },

  IBSCBS_UF_CALC: {
    base_legal:
      "LC 214/2025, Art. 23, §1º — Parcela estadual do IBS; " +
      "Resolução do Comitê Gestor de IBS com alíquotas por UF",
    explicacao:
      "O valor de IBS estadual (vIBSUF) diverge de vBC × pIBSUF. " +
      "A parcela estadual do IBS é apurada separadamente da parcela municipal " +
      "e ambas devem ser informadas individualmente no grupo gIBSCBS.",
    correcao:
      "Recalcule vIBSUF = vBC × pIBSUF utilizando a alíquota do estado de destino " +
      "do produto/serviço. Consulte a tabela de alíquotas estaduais de IBS " +
      "disponível em tribultz.com.br/calculadora/uf-rates.",
  },

  IBSCBS_MUN_CALC: {
    base_legal:
      "LC 214/2025, Art. 23, §2º — Parcela municipal do IBS; " +
      "Resolução do Comitê Gestor de IBS com alíquotas por município",
    explicacao:
      "O valor de IBS municipal (vIBSMun) diverge de vBC × pIBSMun. " +
      "A parcela municipal é destinada ao município de destino do serviço ou " +
      "município do estabelecimento destinatário para operações com bens.",
    correcao:
      "Recalcule vIBSMun = vBC × pIBSMun com a alíquota do município correto. " +
      "Em caso de dúvida sobre o município de destino, consulte o CNPJ destinatário " +
      "e identifique o cMunFG (código do município do fato gerador) na nota.",
  },

  IBSCBS_SPLIT: {
    base_legal:
      "LC 214/2025, Art. 23, §3º — Totalização do IBS = IBS estadual + IBS municipal; " +
      "NT 2025.002-RTC, validação de consistência do grupo gIBSCBS",
    explicacao:
      "O valor total de IBS (vIBS) deve ser exatamente igual à soma de vIBSUF + vIBSMun. " +
      "Inconsistência nessa soma indica erro de preenchimento ou versão desatualizada " +
      "do emissor de notas fiscais.",
    correcao:
      "Corrija vIBS = vIBSUF + vIBSMun antes da transmissão. " +
      "Nenhuma tolerância de arredondamento é aplicada nessa validação de soma.",
  },

  IBSCBS_TOTAL: {
    base_legal:
      "LC 214/2025, Art. 9º, §4º — Consistência dos totalizadores; " +
      "NT 2025.002-RTC, Regra de Totalização dos Grupos de Impostos",
    explicacao:
      "Os totais declarados no grupo <ICMSTot> ou equivalente (vCBS, vIBS) " +
      "não conferem com a soma dos valores individuais por item. " +
      "Essa inconsistência impede a reconciliação fiscal e a apuração de créditos.",
    correcao:
      "Recalcule os totalizadores da nota somando os valores de cada item. " +
      "Certifique-se de que o ERP não aplica arredondamento intermediário " +
      "antes de acumular os totais.",
  },

  CEST_MISSING: {
    base_legal:
      "LC 214/2025, Art. 9º, §5º — CEST obrigatório para substituição tributária; " +
      "Convênio ICMS 92/2015 (lista de produtos com ST, mantida pela reforma)",
    explicacao:
      "O Código Especificador da Substituição Tributária (CEST) é obrigatório " +
      "para produtos sujeitos ao regime de substituição tributária de IBS. " +
      "A ausência impede o correto fluxo de Split Payment e o levantamento " +
      "de créditos de IBS pelo destinatário.",
    correcao:
      "Inclua o campo <CEST> com o código de 7 dígitos correspondente ao NCM do produto " +
      "conforme tabela CEST/ICMS atualizada. Consulte o Convênio ICMS 92/2015 e seus aditivos.",
  },

  CEST_FORMAT: {
    base_legal:
      "Convênio ICMS 92/2015, Cláusula 3ª — Formato obrigatório do CEST: 7 dígitos; " +
      "NT 2025.002-RTC",
    explicacao:
      "O CEST deve conter exatamente 7 dígitos numéricos sem separadores. " +
      "O formato incorreto (6 dígitos, 8 dígitos, letras ou pontos) impede " +
      "a validação pelo SEFAZ e a identificação do produto no regime de ST.",
    correcao:
      "Corrija o campo <CEST> para o formato de 7 dígitos sem formatação " +
      "(ex: 0100100, não 01.001.00). Consulte a tabela CEST oficial do seu segmento.",
  },

  CST_VALID: {
    base_legal:
      "LC 214/2025, Anexo I — Tabela de Códigos de Situação Tributária IBS/CBS; " +
      "NT 2025.002-RTC, Tabela CST",
    explicacao:
      "O CST informado não corresponde a nenhum código válido da tabela oficial " +
      "de CST IBS/CBS. A tabela define códigos como 000 (tributação normal), " +
      "001 (redução), 002 (ad rem), 070 (imunidade/isenção) e 410 (não tributado).",
    correcao:
      "Substitua o CST por um código válido da tabela CST IBS/CBS. " +
      "Consulte a lista completa em /api/v1/public/calculadora/cst-list.",
  },

  CST_GROUP_MATCH: {
    base_legal:
      "NT 2025.002-RTC, Regra de Coerência de Grupo: CST deve corresponder ao grupo XML utilizado",
    explicacao:
      "O CST informado pertence a um grupo tributário (ex: tributação normal) " +
      "mas o item está estruturado em outro grupo XML (ex: isento ou monofásico). " +
      "Essa inconsistência entre código e estrutura XML causa rejeição no SEFAZ.",
    correcao:
      "Alinhe o CST e o grupo XML do item. Se o produto é isento, use CST 070 " +
      "dentro do grupo <ICMS40> ou equivalente. Se é tributado normalmente, " +
      "use CST 000 dentro de <ICMS00>.",
  },

  CST_SEMANTIC: {
    base_legal:
      "LC 214/2025, Art. 9º, §6º — Vedação de tributação em operações imunes ou isentas",
    explicacao:
      "O CST indica imunidade ou isenção (070 ou 410), mas o item declara " +
      "valores de IBS/CBS maiores que zero. Isso é semanticamente incoerente: " +
      "operações imunes ou isentas não geram débito de IBS/CBS.",
    correcao:
      "Se a operação é realmente imune ou isenta, zere os campos vCBS, vIBS, vIBSUF e vIBSMun. " +
      "Se houver tributação, corrija o CST para o código correspondente ao regime efetivo.",
  },

  LAYOUT_PORTAL: {
    base_legal:
      "NT 2025.002-RTC, Seção 4 — Requisitos de Leiaute para Nota Nacional (Nota Fiscal de Serviços Eletrônica Nacional)",
    explicacao:
      "O documento não está em conformidade com o leiaute exigido pelo Portal da Nota Nacional " +
      "para NFS-e. Campos obrigatórios do cabeçalho ou do corpo do documento estão ausentes " +
      "ou fora de posição conforme o XSD publicado pela RFB.",
    correcao:
      "Valide o documento contra o XSD da Nota Nacional disponível no Portal de Documentos " +
      "da Receita Federal. Certifique-se de que o emissor está utilizando a versão de leiaute " +
      "vigente para o período de competência.",
  },

  LAYOUT_NFE: {
    base_legal:
      "NT 2015.003 e atualizações — Leiaute NF-e v4.0; NT 2025.002-RTC — Campos IBS/CBS adicionados ao leiaute",
    explicacao:
      "A NF-e não atende aos requisitos de estrutura do leiaute v4.0 combinados com os " +
      "campos adicionados pela NT 2025.002-RTC para IBS/CBS. Podem estar ausentes campos " +
      "obrigatórios como o grupo gIBSCBS, o campo dhEmi no formato correto, " +
      "ou o grupo de totalização ICMSTot atualizado.",
    correcao:
      "Atualize o emissor de NF-e para suportar o leiaute 4.0 com as extensões da NT 2025.002-RTC. " +
      "Valide contra os XSDs publicados no portal da NF-e (nfe.fazenda.gov.br) " +
      "antes de retransmitir.",
  },
};

/**
 * Retorna a justificativa técnica para um rule_id.
 * Retorna null se o rule_id não tiver justificativa mapeada.
 */
export function getJustification(ruleId: string): FiscalJustification | null {
  return FISCAL_JUSTIFICATIONS[ruleId] ?? null;
}
