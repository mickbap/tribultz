import type {
  Finding,
  FindingSeverity,
  ValidationAuditRef,
  ValidationEvidence,
  ValidationJobRef,
  ValidationResultV11,
  XmlDocumentType,
} from "@/lib/types";
import { lookupNcmSt } from "./cestNcm";

/**
 * Versão da NT 2025.002-RTC que o motor tem como alvo.
 * v1.40 (20/05/2026): novos campos/grupos no IBSCBS (cIndOp, ISUFEmit, gALCZFMCBS,
 * refDFeAnt, gDevTrib ampliado) — tolerados pelo parser. As novas regras de rejeição
 * da v1.40 (B25d-*, BB05-*, C22-*, UB66*…) são rastreadas na issue #311.
 */
export const NT_VERSION = "1.40";

export type ValidationInput = {
  tenantId: string;
  documentType: XmlDocumentType;
  xml: string;
  /** LC 227/2026 art. 348: downgrade obrigações acessórias de FATAL → WARNING. Default: false */
  pedagogicalMode?: boolean;
};

// ── CST table (NT 2025.002-RTC) ────────────────────────────────────────────
// Maps valid CST codes to their required XML group and description.

// ── LC 227/2026 — modo pedagógico ─────────────────────────────────────────
const PEDAGOGICAL_ACCESSORY_RULES = new Set([
  "CST_3_DIGITS", "CCLASSTRIB_6_DIGITS", "SERVICE_CODE_6_DIGITS",
  "CST_VALID", "CST_GROUP_MATCH", "CST_SEMANTIC",
  "IBSCBS_MISSING", "CEST_MISSING", "CEST_FORMAT",
  "LAYOUT_NFE", "LAYOUT_PORTAL", "IMPORT_IBSCBS_REQUIRED",
  "IBSCBSTOT_MISSING",
]);

const LC227_NOTE =
  " — Período Pedagógico LC 227/2026 (art. 348 §§ 3º e 4º): " +
  "se autuado exclusivamente por esta obrigação acessória, " +
  "há 60 dias para regularizar sem aplicação de multa.";

// ── NT 2025.002 v1.40 — códigos de rejeição SEFAZ (#311) ─────────────────────
// Anota o código oficial de rejeição nas detecções que o antecipam (NF-e/NFC-e),
// para o usuário saber exatamente como a SEFAZ rejeitará. Precedente: Rejeição 1157.
const REJECTION_CODES: Record<string, string> = {
  IBSCBS_MISSING:
    " — SEFAZ: Rejeição 1115 (regra UB12-10): preenchimento de IBS/CBS obrigatório — " +
    "produção a partir de 03/08/2026 (Regime Normal/CRT 3) e 04/01/2027 (Simples/MEI), NT 2025.002 v1.40.",
  CCLASSTRIB_6_DIGITS:
    " — SEFAZ: Rejeição 1106 (regra LA01-30) / 960 (regra N12-110): cClassTrib obrigatório " +
    "e com classificação tributária adequada (NT 2025.002 v1.40).",
  // Grupo W03 (Total da NF-e — IBS/CBS/IS) — #403
  IBSCBSTOT_MISSING:
    " — SEFAZ: Rejeição 1119 (regra W34-20): grupo de totais IBSCBSTot (W03) obrigatório quando " +
    "algum item informa IBS/CBS — produção a partir de 03/08/2026 (Regime Normal/CRT 3) " +
    "e 04/01/2027 (Simples/MEI), NT 2025.002 v1.40.",
  IBSCBSTOT_UNDUE:
    " — SEFAZ: Rejeição 1118 (regra W34-10): grupo IBSCBSTot informado sem nenhum item " +
    "com IBS/CBS (NT 2025.002 v1.40).",
  IBSCBS_TOTAL:
    " — SEFAZ: Rejeição 1091 (regra W56-10, total CBS) / 1085 (regra W47-10, total IBS): " +
    "os totais do IBSCBSTot devem ser a soma dos campos correspondentes dos itens (NT 2025.002 v1.40).",
};

// ── Ato Conjunto RFB/CGIBS nº 1/2025 — janela sem penalidades ─────────────────
// Art. 3º: penalidades por descumprimento de obrigações acessórias de IBS/CBS
// ficam suspensas até o 1º dia do 4º mês subsequente à publicação da parte comum
// dos regulamentos (Decreto 12.955/2026 + Resolução CGIBS 6/2026, publicados em
// 30/04/2026). Logo: sem multa para fatos geradores até 31/07/2026; a partir de
// 01/08/2026 a penalidade volta a ser aplicável → severidade FATAL.
// A dispensa de *recolhimento* (pagamento) cobre 2026 inteiro, mas aqui tratamos
// apenas a suspensão de *multa* por obrigação acessória (o que o motor valida).
const NO_PENALTY_WINDOW_START = "2026-01-01";
const NO_PENALTY_WINDOW_END = "2026-08-01"; // exclusivo: notas a partir desta data são penalizáveis

const ATO_CONJUNTO_NOTE =
  " — Período sem penalidades (Ato Conjunto RFB/CGIBS nº 1/2025, art. 3º): " +
  "obrigação acessória de IBS/CBS sem multa para fatos geradores até 31/07/2026 " +
  "(parte comum dos regulamentos publicada em 30/04/2026). " +
  "A partir de 01/08/2026 a penalidade é aplicável.";

/** Data de emissão (dhEmi/NFS-e) dentro da janela sem penalidades do Ato Conjunto 1/25. */
function isWithinNoPenaltyWindow(emissionDate: string | undefined): boolean {
  if (!emissionDate) return false;
  const datePart = emissionDate.slice(0, 10); // YYYY-MM-DD
  if (!/^\d{4}-\d{2}-\d{2}$/.test(datePart)) return false;
  // Comparação lexicográfica é válida para datas ISO YYYY-MM-DD.
  return datePart >= NO_PENALTY_WINDOW_START && datePart < NO_PENALTY_WINDOW_END;
}

// ── Comunicado Conjunto CGIBS/RFB nº 01/2025 — CNPJ p/ PF contribuinte ───────
// A partir de 01/07/2026, a pessoa física contribuinte de IBS/CBS deve se inscrever
// no CNPJ e não pode emitir documento fiscal por CPF (LC 214 art. 251). O enquadramento
// como contribuinte (atividade habitual; locação com >3 imóveis e renda > R$ 240 mil/ano)
// não é verificável do XML — por isso a regra é ALERT informativo (verificar enquadramento).
// Decreto 13.075/2026 (altera o Decreto 12.955/2026, art. 239) adiou de
// 01/07/2026 para 01/01/2027 — não editar sem checar se um decreto mais
// recente adiou de novo.
const PF_CNPJ_REQUIRED_DATE = "2027-01-01";

// NF-e de devolução (finNFe=4): a partir de 01/09/2026 referencia a nota original por item,
// exclusivamente via grupo DFeReferenciado (v1.40, Rejeição 321 — VC02-14/VC03-20).
const DEVOLUCAO_DFEREF_DATE = "2026-09-01";

// DANFE Simplificado Tipo 2 (tpImp=6, NT 2026.002 v1.00): a partir de 03/08/2026 (produção,
// fase 2), a NF-e (modelo 55) restringe-se a saída/interna/sem NFref/finalidade Normal (#405).
const DANFE_T2_PRODUCAO_DATE = "2026-08-03";

// ── CST table (NT 2025.002-RTC) ────────────────────────────────────────────
export const CST_TABLE: Record<string, { group: string | null; description: string }> = {
  "000": { group: "gIBSCBS", description: "Tributação normal (ad valorem)" },
  "001": { group: "gIBSCBS", description: "Tributação normal com redução de base" },
  "002": { group: "gIBSCBSMono", description: "Tributação ad rem" },
  "070": { group: null, description: "Imunidade / Isenção" },
  "200": { group: "gIBSCBS", description: "Diferimento" },
  "410": { group: null, description: "Suspensão" },
  "510": { group: "gIBSCBS", description: "Crédito presumido" },
  "515": { group: "gIBSCBS", description: "Crédito presumido especial" },
  "550": { group: "gIBSCBS", description: "Regime específico" },
  "620": { group: "gIBSCBSMono", description: "Monofásico" },
  "800": { group: "gTransfCred", description: "Transferência de crédito" },
  "810": { group: null, description: "Ressarcimento" },
  "811": { group: "gAjusteCompet", description: "Ajuste de competência" },
  "830": { group: "gEstornoCred", description: "Estorno de crédito" },
};

const VALID_CST_CODES = new Set(Object.keys(CST_TABLE));

// ── Helpers ─────────────────────────────────────────────────────────────────

function fnv1a32(value: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
}

function nowIso(): string {
  return new Date().toISOString();
}

function firstTag(xml: string, tags: string[]): { tag: string; value: string; snippet: string; index: number } | null {
  for (const tag of tags) {
    // Use word-boundary-like pattern: tag must be followed by > or whitespace, not more word chars
    const re = new RegExp(`<${tag}(?=[\\s>/])([^>]*)>([\\s\\S]*?)<\\/${tag}>`, "i");
    const match = re.exec(xml);
    if (match) {
      return {
        tag,
        value: String(match[2] ?? "").trim(),
        snippet: match[0],
        index: match.index,
      };
    }
  }
  return null;
}

/** Valida o DV da Inscrição SUFRAMA (9 díg; módulo 11, pesos 2–9 da direita p/ esquerda;
 * resto 0/1 → DV 0). Regra SUFRAMA_DV (C22-20, #311). */
function suframaDvOk(inscricao: string): boolean {
  const digits = (inscricao.match(/\d/g) ?? []).join("");
  if (digits.length !== 9) return false;
  const weights = [9, 8, 7, 6, 5, 4, 3, 2];
  let total = 0;
  for (let i = 0; i < 8; i++) total += Number(digits[i]) * weights[i];
  let calc = 11 - (total % 11);
  if (calc >= 10) calc = 0;
  return calc === Number(digits[8]);
}

/** Returns ALL matches for a tag (useful for multi-item NF-e). */
function allTags(xml: string, tag: string): { value: string; snippet: string; index: number }[] {
  const re = new RegExp(`<${tag}(?=[\\s>/])([^>]*)>([\\s\\S]*?)<\\/${tag}>`, "gi");
  const results: { value: string; snippet: string; index: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(xml)) !== null) {
    results.push({ value: String(m[2] ?? "").trim(), snippet: m[0], index: m.index });
  }
  return results;
}

function inferXpath(tag: string, documentType: XmlDocumentType): string {
  const base = documentType === "NFSE" ? "/NFS-e/infNfse" : "/nfeProc/NFe/infNFe";
  return `${base}//${tag}`;
}

function makeEvidenceId(seed: string): string {
  return `E_XML_${seed}`;
}

function makeFinding(args: {
  id: string;
  severity: FindingSeverity;
  ruleId: string;
  title: string;
  field: string;
  xpath?: string;
  snippet?: string;
  evidenceId: string;
  recommendation?: string;
}): Finding {
  return {
    id: args.id,
    severity: args.severity,
    rule_id: args.ruleId,
    title: args.title,
    where: {
      field: args.field,
      xpath: args.xpath,
      snippet: args.snippet,
    },
    recommendation: args.recommendation ?? "Corrigir no ERP e reemitir (com justificativa se necessário).",
    evidence_ids: [args.evidenceId],
  };
}

function makeEvidence(args: {
  id: string;
  type: ValidationEvidence["type"];
  label: string;
  href?: string;
  xpath?: string;
  snippet?: string;
}): ValidationEvidence {
  return {
    id: args.id,
    type: args.type,
    label: args.label,
    href: args.href,
    xpath: args.xpath,
    snippet: args.snippet,
  };
}

function pushFindingAndEvidence(
  findings: Finding[],
  evidences: ValidationEvidence[],
  evidenceById: Set<string>,
  finding: Finding,
  evidence: ValidationEvidence,
) {
  findings.push(finding);
  if (!evidenceById.has(evidence.id)) {
    evidences.push(evidence);
    evidenceById.add(evidence.id);
  }
}

/** Detect whether XML is NF-e/NFC-e (has IBSCBS group) vs NFS-e legacy. */
function isNfeLayout(xml: string): boolean {
  return /<IBSCBS[\s>]/i.test(xml) || /<nfeProc[\s>]/i.test(xml) || /<infNFe[\s>]/i.test(xml);
}

/** Auto-detect document type from XML content. */
export function detectDocumentType(xml: string): XmlDocumentType {
  if (/<mod>\s*65\s*<\/mod>/i.test(xml)) return "NFCE";
  if (/<nfeProc[\s>]/i.test(xml) || /<infNFe[\s>]/i.test(xml)) return "NFE";
  return "NFSE";
}

// ── Main validation ─────────────────────────────────────────────────────────

export function validateXmlWithRules(input: ValidationInput): ValidationResultV11 {
  const xml = input.xml.trim();
  const fingerprint = fnv1a32(`${input.documentType}|${xml}`);
  const jobId = `job_xml_${fingerprint}`;
  const auditId = `audit_xml_${fingerprint}`;
  const pedMode = input.pedagogicalMode === true;

  const findings: Finding[] = [];
  const evidences: ValidationEvidence[] = [];
  const evidenceById = new Set<string>();

  const docType = input.documentType;
  const isNfe = docType === "NFE" || docType === "NFCE";
  const hasIbscbsGroup = isNfeLayout(xml);

  // ── Shared field extraction ───────────────────────────────────────────────

  // For NF-e, extract CST and cClassTrib from inside the IBSCBS group to avoid
  // picking up ICMS CST (which can be 2-digit "00") instead of IBSCBS CST ("000").
  const ibscbsBlock = firstTag(xml, ["IBSCBS"]);
  const cst = hasIbscbsGroup && ibscbsBlock
    ? firstTag(ibscbsBlock.snippet, ["CST"])
    : firstTag(xml, ["CST"]);
  const cClassTrib = hasIbscbsGroup && ibscbsBlock
    ? firstTag(ibscbsBlock.snippet, ["cClassTrib"])
    : firstTag(xml, ["cClassTrib"]);
  const ncm = firstTag(xml, ["NCM"]);
  const cest = firstTag(xml, ["CEST"]);

  // dPrevEntrega fields (NT 2025.002 V1.36 + Cartilha CGIBS item 1.1)
  const dPrevEntrega = firstTag(xml, ["dPrevEntrega"]);
  const dhEmi = firstTag(xml, ["dhEmi"]);
  const modFrete = firstTag(xml, ["modFrete"]);

  // Data de emissão para a janela sem penalidades (Ato Conjunto 1/25): NF-e usa
  // dhEmi; NFS-e legado usa DataEmissao/dhEmissao/dhProc/dEmi. Mantemos dhEmi
  // separado para as regras de competência (dPrevEntrega).
  const emissionDate = dhEmi ?? firstTag(xml, ["DataEmissao", "dhEmissao", "dhProc", "dEmi"]);

  // NFS-e legacy fields
  const serviceCode = firstTag(xml, ["CodigoServico", "cServ", "codigoServico"]);
  const valorCbs = firstTag(xml, ["ValorCBS", "vCBS"]);
  const valorIbs = firstTag(xml, ["ValorIBS", "vIBS"]);
  const aliquotaCbs = firstTag(xml, ["AliquotaCBS", "pCBS"]);
  const aliquotaIbs = firstTag(xml, ["AliquotaIBS", "pIBSUF", "pIBSMun"]);
  const baseCalculo = firstTag(xml, ["BaseCalculo", "vBC"]);

  // NFS-e — grupo IBSCBS da DPS, NT 004 v2.00/005/007 (#406). indZFMALC sinaliza
  // operação com alíquota zero de CBS (Zona Franca de Manaus/Área de Livre
  // Comércio). vPis/vCofins: a partir da NT 007/2026 informam apenas o valor
  // DEVIDO (não retido).
  const indZfmalc = firstTag(xml, ["indZFMALC", "IndZFMALC"]);
  const vPis = firstTag(xml, ["vPis", "ValorPis"]);
  const vCofins = firstTag(xml, ["vCofins", "ValorCofins"]);

  // Grupo "piscofins" (NFSe/infNFSe/DPS/infDPS/valores/trib/tribFed/piscofins) —
  // vBCPisCofins/pAliqPis/pAliqCofins são campos irmãos de vPis/vCofins, todos
  // opcionais (#480). Fórmula confirmada via fonte oficial + manual de integração
  // pós-NT007 (ver comentário na regra PIS_COFINS_DEVIDO_CALC abaixo).
  const baseCalculoPisCofins = firstTag(xml, ["vBCPisCofins", "BaseCalculoPisCofins"]);
  const aliquotaPis = firstTag(xml, ["pAliqPis", "AliquotaPis"]);
  const aliquotaCofins = firstTag(xml, ["pAliqCofins", "AliquotaCofins"]);

  // NF-e IBSCBS group fields
  const vBC = firstTag(xml, ["vBC"]);
  const pCBS = firstTag(xml, ["pCBS"]);
  const vCBS = firstTag(xml, ["vCBS"]);
  const pIBSUF = firstTag(xml, ["pIBSUF"]);
  const vIBSUF = firstTag(xml, ["vIBSUF"]);
  const pIBSMun = firstTag(xml, ["pIBSMun"]);
  const vIBSMun = firstTag(xml, ["vIBSMun"]);
  const vIBS = firstTag(xml, ["vIBS"]);

  // CRT do emitente (NT 2025.002 v1.40 #311): 1/2=Simples Nacional, 3=Regime Normal, 4=MEI.
  // Obrigatoriedade de IBS/CBS é faseada: Simples/MEI só a partir de 04/01/2027 → WARNING,
  // não FATAL (evita falso-rejeitar); Regime Normal (CRT 3) segue o cronograma (03/08/2026).
  const crt = firstTag(xml, ["CRT"]);
  const crtVal = crt?.value?.trim() ?? "";
  const isSimplesOrMei = crtVal === "1" || crtVal === "2" || crtVal === "4";
  // Simples/MEI: WARNING por faseamento (obrigatório só 04/01/2027). Demais: FATAL —
  // o downgrade por pedagogicalMode (LC 227) e pela janela sem penalidades (Ato
  // Conjunto 1/25) é centralizado no passe final, como nas outras regras acessórias.
  const ibsCbsMissingSev: FindingSeverity = isSimplesOrMei ? "WARNING" : "FATAL";
  const SIMPLES_MEI_NOTE =
    " Simples Nacional/MEI: obrigatório a partir de 04/01/2027 (NT 2025.002 v1.40).";

  // NF-e totals
  const ibscbsTot = firstTag(xml, ["IBSCBSTot"]);
  const totVIBS = ibscbsTot ? firstTag(ibscbsTot.snippet, ["vIBS"]) : null;
  const totVCBS = ibscbsTot ? firstTag(ibscbsTot.snippet, ["vCBS"]) : null;

  // Split payment (#276) — <cobr>/<dup>/<indPag>
  const indPag = firstTag(xml, ["indPag"]);
  // CSTs que legitimamente não destacam IBS/CBS no estágio atual: imunidade/isenção
  // (070), diferimento (200), suspensão (410) e transferência/ressarcimento/ajuste/
  // estorno de crédito (800/810/811/830).
  const NO_TAX_CSTS = new Set(["070", "200", "410", "800", "810", "811", "830"]);

  // ── Rules 1-3: field format checks ────────────────────────────────────────

  const formatFields = [
    {
      findingId: "F_CST_LEN",
      ruleId: "CST_3_DIGITS",
      title: "CST inválido (esperado 3 dígitos)",
      field: "CST",
      source: cst,
      test: (value: string) => /^\d{3}$/.test(value),
    },
    {
      findingId: "F_CCLASSTRIB_LEN",
      ruleId: "CCLASSTRIB_6_DIGITS",
      title: "ClassTrib incorreto (esperado 6 dígitos conforme categoria do negócio)",
      field: "cClassTrib",
      source: cClassTrib,
      test: (value: string) => /^\d{6}$/.test(value),
    },
    {
      findingId: "F_SERVICE_CODE_LEN",
      ruleId: "SERVICE_CODE_6_DIGITS",
      title: "Código de serviço inválido (esperado 6 dígitos)",
      field: "CodigoServico",
      source: serviceCode,
      test: (value: string) => /^\d{6}$/.test(value),
      skipIf: isNfe, // NF-e uses CFOP, not CodigoServico
    },
  ] as const;

  for (const row of formatFields) {
    if ("skipIf" in row && row.skipIf) continue;
    const evId = makeEvidenceId(row.findingId.replace(/^F_/, ""));
    const xpath = row.source ? inferXpath(row.source.tag, docType) : inferXpath(row.field, docType);
    const snippet = row.source?.snippet ?? `<!-- Campo ${row.field} não encontrado no XML -->`;
    const value = row.source?.value ?? "";
    if (!row.test(value)) {
      findings.push(
        makeFinding({
          id: row.findingId,
          severity: "FATAL",
          ruleId: row.ruleId,
          title: row.title,
          field: row.field,
          xpath,
          snippet,
          evidenceId: evId,
        }),
      );
    }
    if (!evidenceById.has(evId)) {
      evidences.push(
        makeEvidence({ id: evId, type: "xml", label: `Trecho XML — ${row.field}`, xpath, snippet }),
      );
      evidenceById.add(evId);
    }
  }

  // ── Rule 4: CST_VALID — CST must be a known code (NT 2025.002, NF-e only) ─

  if (hasIbscbsGroup && cst && /^\d{3}$/.test(cst.value) && !VALID_CST_CODES.has(cst.value)) {
    const evId = makeEvidenceId("CST_VALID");
    pushFindingAndEvidence(findings, evidences, evidenceById,
      makeFinding({
        id: "F_CST_VALID",
        severity: "FATAL",
        ruleId: "CST_VALID",
        title: `CST "${cst.value}" não é código válido conforme NT 2025.002-RTC`,
        field: "CST",
        xpath: inferXpath("CST", docType),
        snippet: cst.snippet,
        evidenceId: evId,
        recommendation: `CSTs válidos: ${[...VALID_CST_CODES].join(", ")}. Corrigir conforme classificação tributária.`,
      }),
      makeEvidence({ id: evId, type: "xml", label: "CST — código desconhecido", xpath: inferXpath("CST", docType), snippet: cst.snippet }),
    );
  }

  // ── Rule 5: CST_GROUP_MATCH — CST ↔ XML group coherence ──────────────────

  if (hasIbscbsGroup && cst && /^\d{3}$/.test(cst.value) && VALID_CST_CODES.has(cst.value)) {
    const expectedGroup = CST_TABLE[cst.value]?.group;
    if (expectedGroup) {
      const groupPresent = !!firstTag(xml, [expectedGroup]);
      if (!groupPresent) {
        const evId = makeEvidenceId("CST_GROUP_MATCH");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_CST_GROUP_MATCH",
            severity: "FATAL",
            ruleId: "CST_GROUP_MATCH",
            title: `CST ${cst.value} exige grupo <${expectedGroup}> que não foi encontrado`,
            field: "IBSCBS",
            xpath: inferXpath("IBSCBS", docType),
            snippet: cst.snippet,
            evidenceId: evId,
            recommendation: `CST ${cst.value} (${CST_TABLE[cst.value]?.description}) requer o grupo XML <${expectedGroup}>. Preencher conforme NT 2025.002.`,
          }),
          makeEvidence({ id: evId, type: "xml", label: `CST ${cst.value} — grupo ausente`, xpath: inferXpath("IBSCBS", docType), snippet: cst.snippet }),
        );
      }
    }
    // CST 070/410 should NOT have tax values > 0
    if (cst.value === "070" || cst.value === "410") {
      const taxVal = parseFloat(vCBS?.value ?? valorCbs?.value ?? "0");
      const ibsTaxVal = parseFloat(vIBS?.value ?? valorIbs?.value ?? "0");
      if (taxVal > 0 || ibsTaxVal > 0) {
        const evId = makeEvidenceId("CST_SEMANTIC");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_CST_SEMANTIC",
            severity: "FATAL",
            ruleId: "CST_SEMANTIC",
            title: `CST ${cst.value} (${CST_TABLE[cst.value]?.description}) não deve ter valores tributários > 0`,
            field: "IBS/CBS",
            xpath: inferXpath("IBSCBS", docType),
            snippet: cst.snippet,
            evidenceId: evId,
            recommendation: `CST ${cst.value} indica imunidade/isenção/suspensão — valores CBS e IBS devem ser zero.`,
          }),
          makeEvidence({ id: evId, type: "xml", label: `CST ${cst.value} — valor incoerente`, xpath: inferXpath("IBSCBS", docType), snippet: cst.snippet }),
        );
      }
    }

    // CST 620 (monofásico): operações downstream devem ter vCBS = vIBS = 0 (#277)
    if (cst.value === "620") {
      const taxVal = parseFloat(vCBS?.value ?? valorCbs?.value ?? "0");
      const ibsTaxVal = parseFloat(vIBS?.value ?? valorIbs?.value ?? "0");
      if (taxVal > 0 || ibsTaxVal > 0) {
        const evId = makeEvidenceId("MONOFASICO_ZERO");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_MONOFASICO_ZERO",
            severity: "FATAL",
            ruleId: "MONOFASICO_ZERO",
            title: `CST 620 (Monofásico) não deve ter valores tributários > 0 — recolhimento é do fabricante/importador`,
            field: "IBS/CBS",
            xpath: inferXpath("IBSCBS", docType),
            snippet: cst.snippet,
            evidenceId: evId,
            recommendation: `CST 620 (regime monofásico): o IBS/CBS é recolhido integralmente pelo fabricante/importador. Operações downstream devem ter vCBS=0 e vIBS=0 (Reg. CBS cap. 8 / Reg. IBS cap. 6). Valor > 0 indica duplo recolhimento.`,
          }),
          makeEvidence({ id: evId, type: "xml", label: `CST 620 — valor monofásico incoerente`, xpath: inferXpath("IBSCBS", docType), snippet: cst.snippet }),
        );
      }
    }
  }

  // ── Rule 6: IBSCBS_MISSING — IBS/CBS fields must be present ──────────────

  if (hasIbscbsGroup) {
    // NF-e path: check IBSCBS group exists
    const ibscbsTag = firstTag(xml, ["IBSCBS"]);
    if (!ibscbsTag) {
      const evId = makeEvidenceId("IBSCBS_MISSING");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_IBSCBS_MISSING",
          severity: ibsCbsMissingSev,
          ruleId: "IBSCBS_MISSING",
          title: "Grupo IBSCBS ausente — obrigatório conforme NT 2025.002",
          field: "IBSCBS",
          xpath: inferXpath("imposto", docType),
          snippet: "<!-- Grupo <IBSCBS> não encontrado em <imposto> -->",
          evidenceId: evId,
          recommendation:
            "Informar grupo IBSCBS com CST, cClassTrib e campos de cálculo conforme NT 2025.002." +
            (isSimplesOrMei ? SIMPLES_MEI_NOTE : ""),
        }),
        makeEvidence({ id: evId, type: "xml", label: "IBSCBS — grupo ausente", xpath: inferXpath("imposto", docType), snippet: "<!-- Grupo <IBSCBS> não encontrado -->" }),
      );
    }
  } else {
    // NFS-e legacy path
    const hasIbsCbs = !!(valorCbs && valorIbs && aliquotaCbs && aliquotaIbs);
    if (!hasIbsCbs) {
      const evId = makeEvidenceId("IBSCBS_MISSING");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_IBSCBS_MISSING",
          severity: ibsCbsMissingSev,
          ruleId: "IBSCBS_MISSING",
          title: "IBS/CBS ausentes na nota — obrigatório informar percentual e valor",
          field: "IBS/CBS",
          xpath: inferXpath("Valores", docType),
          snippet: "<!-- Tags ValorCBS, ValorIBS, AliquotaCBS, AliquotaIBS não encontradas -->",
          evidenceId: evId,
          recommendation:
            "Informar alíquota e valor de IBS (0,90%) e CBS (0,10%) conforme LC 214." +
            (isSimplesOrMei ? SIMPLES_MEI_NOTE : ""),
        }),
        makeEvidence({ id: evId, type: "xml", label: "IBS/CBS — campos ausentes", xpath: inferXpath("Valores", docType), snippet: "<!-- Tags ValorCBS, ValorIBS, AliquotaCBS, AliquotaIBS não encontradas -->" }),
      );
    }
  }

  // ── Rule 7: IBSCBS_CALC — CBS calculation check ──────────────────────────

  if (hasIbscbsGroup && vBC && pCBS && vCBS) {
    // NF-e: vCBS == vBC × pCBS
    const base = parseFloat(vBC.value);
    const rate = parseFloat(pCBS.value);
    const declared = parseFloat(vCBS.value);
    if (!isNaN(base) && !isNaN(rate) && !isNaN(declared)) {
      const expected = base * rate;
      if (Math.abs(declared - expected) > 0.01) {
        const evId = makeEvidenceId("IBSCBS_CALC_CBS");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_IBSCBS_CALC_CBS",
            severity: "FATAL",
            ruleId: "IBSCBS_CALC",
            title: `CBS incorreto — informado R$ ${declared.toFixed(2)}, esperado R$ ${expected.toFixed(2)}`,
            field: "vCBS",
            xpath: inferXpath("vCBS", docType),
            snippet: vCBS.snippet,
            evidenceId: evId,
            recommendation: `vCBS deve ser vBC (${base.toFixed(2)}) × pCBS (${rate}) = R$ ${expected.toFixed(2)}.`,
          }),
          makeEvidence({ id: evId, type: "xml", label: "CBS — cálculo divergente", xpath: inferXpath("vCBS", docType), snippet: vCBS.snippet }),
        );
      }
    }
  } else if (!hasIbscbsGroup && valorCbs && aliquotaCbs && baseCalculo) {
    // NFS-e legacy CBS check
    const base = parseFloat(baseCalculo.value);
    const cbsVal = parseFloat(valorCbs.value);
    const cbsRate = parseFloat(aliquotaCbs.value);
    if (!isNaN(base) && !isNaN(cbsVal) && !isNaN(cbsRate)) {
      const expectedCbs = base * cbsRate;
      if (Math.abs(cbsVal - expectedCbs) > 0.01) {
        const evId = makeEvidenceId("IBSCBS_CALC_CBS");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_IBSCBS_CALC_CBS",
            severity: "FATAL",
            ruleId: "IBSCBS_CALC",
            title: `Cálculo CBS incorreto — informado R$ ${cbsVal.toFixed(2)}, esperado R$ ${expectedCbs.toFixed(2)}`,
            field: "ValorCBS",
            xpath: inferXpath("ValorCBS", docType),
            snippet: valorCbs.snippet,
            evidenceId: evId,
            recommendation: `CBS deve ser Base (${base.toFixed(2)}) × Alíquota (${cbsRate}) = R$ ${expectedCbs.toFixed(2)}. Corrigir valor.`,
          }),
          makeEvidence({ id: evId, type: "xml", label: "CBS — cálculo divergente", xpath: inferXpath("ValorCBS", docType), snippet: valorCbs.snippet }),
        );
      }
    }
  }

  // ── Rule 7b: IBS calculation check (NFS-e legacy) ────────────────────────

  if (!hasIbscbsGroup && valorIbs && aliquotaIbs && baseCalculo) {
    const base = parseFloat(baseCalculo.value);
    const ibsVal = parseFloat(valorIbs.value);
    const ibsRate = parseFloat(aliquotaIbs.value);
    if (!isNaN(base) && !isNaN(ibsVal) && !isNaN(ibsRate)) {
      const expectedIbs = base * ibsRate;
      if (Math.abs(ibsVal - expectedIbs) > 0.01) {
        const evId = makeEvidenceId("IBSCBS_CALC_IBS");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_IBSCBS_CALC_IBS",
            severity: "FATAL",
            ruleId: "IBSCBS_CALC",
            title: `Cálculo IBS incorreto — informado R$ ${ibsVal.toFixed(2)}, esperado R$ ${expectedIbs.toFixed(2)}`,
            field: "ValorIBS",
            xpath: inferXpath("ValorIBS", docType),
            snippet: valorIbs.snippet,
            evidenceId: evId,
            recommendation: `IBS deve ser Base (${base.toFixed(2)}) × Alíquota (${ibsRate}) = R$ ${expectedIbs.toFixed(2)}. Corrigir valor.`,
          }),
          makeEvidence({ id: evId, type: "xml", label: "IBS — cálculo divergente", xpath: inferXpath("ValorIBS", docType), snippet: valorIbs.snippet }),
        );
      }
    }
  }

  // ── Rule 11: IBSCBS_UF_CALC — vIBSUF == vBC × pIBSUF (NF-e only) ───────

  if (hasIbscbsGroup && vBC && pIBSUF && vIBSUF) {
    const base = parseFloat(vBC.value);
    const rate = parseFloat(pIBSUF.value);
    const declared = parseFloat(vIBSUF.value);
    if (!isNaN(base) && !isNaN(rate) && !isNaN(declared)) {
      const expected = base * rate;
      if (Math.abs(declared - expected) > 0.01) {
        const evId = makeEvidenceId("IBSCBS_UF_CALC");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_IBSCBS_UF_CALC",
            severity: "FATAL",
            ruleId: "IBSCBS_UF_CALC",
            title: `IBS UF incorreto — informado R$ ${declared.toFixed(2)}, esperado R$ ${expected.toFixed(2)}`,
            field: "vIBSUF",
            xpath: inferXpath("vIBSUF", docType),
            snippet: vIBSUF.snippet,
            evidenceId: evId,
            recommendation: `vIBSUF deve ser vBC (${base.toFixed(2)}) × pIBSUF (${rate}) = R$ ${expected.toFixed(2)}.`,
          }),
          makeEvidence({ id: evId, type: "xml", label: "IBS UF — cálculo divergente", xpath: inferXpath("vIBSUF", docType), snippet: vIBSUF.snippet }),
        );
      }
    }
  }

  // ── Rule 12: IBSCBS_MUN_CALC — vIBSMun == vBC × pIBSMun (NF-e only) ────

  if (hasIbscbsGroup && vBC && pIBSMun && vIBSMun) {
    const base = parseFloat(vBC.value);
    const rate = parseFloat(pIBSMun.value);
    const declared = parseFloat(vIBSMun.value);
    if (!isNaN(base) && !isNaN(rate) && !isNaN(declared)) {
      const expected = base * rate;
      if (Math.abs(declared - expected) > 0.01) {
        const evId = makeEvidenceId("IBSCBS_MUN_CALC");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_IBSCBS_MUN_CALC",
            severity: "FATAL",
            ruleId: "IBSCBS_MUN_CALC",
            title: `IBS Municipal incorreto — informado R$ ${declared.toFixed(2)}, esperado R$ ${expected.toFixed(2)}`,
            field: "vIBSMun",
            xpath: inferXpath("vIBSMun", docType),
            snippet: vIBSMun.snippet,
            evidenceId: evId,
            recommendation: `vIBSMun deve ser vBC (${base.toFixed(2)}) × pIBSMun (${rate}) = R$ ${expected.toFixed(2)}.`,
          }),
          makeEvidence({ id: evId, type: "xml", label: "IBS Municipal — cálculo divergente", xpath: inferXpath("vIBSMun", docType), snippet: vIBSMun.snippet }),
        );
      }
    }
  }

  // ── Rule 13: IBSCBS_SPLIT — vIBS == vIBSUF + vIBSMun (NF-e only) ───────

  if (hasIbscbsGroup && vIBS && vIBSUF && vIBSMun) {
    const total = parseFloat(vIBS.value);
    const uf = parseFloat(vIBSUF.value);
    const mun = parseFloat(vIBSMun.value);
    if (!isNaN(total) && !isNaN(uf) && !isNaN(mun)) {
      const expected = uf + mun;
      if (Math.abs(total - expected) > 0.01) {
        const evId = makeEvidenceId("IBSCBS_SPLIT");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_IBSCBS_SPLIT",
            severity: "FATAL",
            ruleId: "IBSCBS_SPLIT",
            title: `Split IBS incorreto — vIBS (${total.toFixed(2)}) ≠ vIBSUF (${uf.toFixed(2)}) + vIBSMun (${mun.toFixed(2)})`,
            field: "vIBS",
            xpath: inferXpath("vIBS", docType),
            snippet: vIBS.snippet,
            evidenceId: evId,
            recommendation: `vIBS deve ser igual a vIBSUF + vIBSMun = R$ ${expected.toFixed(2)}.`,
          }),
          makeEvidence({ id: evId, type: "xml", label: "IBS — split UF/Municipal divergente", xpath: inferXpath("vIBS", docType), snippet: vIBS.snippet }),
        );
      }
    }
  }

  // ── Rule 14: IBSCBS_TOTAL — IBSCBSTot consistency (NF-e only) ────────────

  if (hasIbscbsGroup && ibscbsTot) {
    // Sum item-level vCBS and vIBS across all <det> items
    const itemVCBS = allTags(xml, "vCBS");
    const itemVIBS = allTags(xml, "vIBS");
    // Exclude the last occurrence (which is the total) if IBSCBSTot exists
    const detVCBS = itemVCBS.slice(0, -1);
    const detVIBS = itemVIBS.slice(0, -1);

    if (totVCBS && detVCBS.length > 0) {
      const declaredTotal = parseFloat(totVCBS.value);
      const sumItems = detVCBS.reduce((acc, i) => acc + (parseFloat(i.value) || 0), 0);
      if (!isNaN(declaredTotal) && Math.abs(declaredTotal - sumItems) > 0.01) {
        const evId = makeEvidenceId("IBSCBS_TOTAL_CBS");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_IBSCBS_TOTAL_CBS",
            severity: "FATAL",
            ruleId: "IBSCBS_TOTAL",
            title: `Total CBS (${declaredTotal.toFixed(2)}) ≠ soma dos itens (${sumItems.toFixed(2)})`,
            field: "IBSCBSTot/vCBS",
            xpath: inferXpath("IBSCBSTot", docType),
            snippet: totVCBS.snippet,
            evidenceId: evId,
            recommendation: `IBSCBSTot.vCBS deve ser a soma dos vCBS de cada item.`,
          }),
          makeEvidence({ id: evId, type: "xml", label: "Total CBS — divergente", xpath: inferXpath("IBSCBSTot", docType), snippet: totVCBS.snippet }),
        );
      }
    }

    if (totVIBS && detVIBS.length > 0) {
      const declaredTotal = parseFloat(totVIBS.value);
      const sumItems = detVIBS.reduce((acc, i) => acc + (parseFloat(i.value) || 0), 0);
      if (!isNaN(declaredTotal) && Math.abs(declaredTotal - sumItems) > 0.01) {
        const evId = makeEvidenceId("IBSCBS_TOTAL_IBS");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_IBSCBS_TOTAL_IBS",
            severity: "FATAL",
            ruleId: "IBSCBS_TOTAL",
            title: `Total IBS (${declaredTotal.toFixed(2)}) ≠ soma dos itens (${sumItems.toFixed(2)})`,
            field: "IBSCBSTot/vIBS",
            xpath: inferXpath("IBSCBSTot", docType),
            snippet: totVIBS.snippet,
            evidenceId: evId,
            recommendation: `IBSCBSTot.vIBS deve ser a soma dos vIBS de cada item.`,
          }),
          makeEvidence({ id: evId, type: "xml", label: "Total IBS — divergente", xpath: inferXpath("IBSCBSTot", docType), snippet: totVIBS.snippet }),
        );
      }
    }
  }

  // ── Rules 14b/14c: W03 — presença do IBSCBSTot (#403, NT v1.40) ──────────
  // Grupo W03 (Total da NF-e — IBS/CBS/IS): a SEFAZ valida presença nas duas
  // direções (regras W34-10/W34-20). allTags("IBSCBS") não casa <IBSCBSTot>
  // (lookahead exige espaço/>/ após o nome da tag).

  if (hasIbscbsGroup) {
    const itemIbscbsBlocks = allTags(xml, "IBSCBS");

    // W34-20 → Rejeição 1119: item informa IBS/CBS mas IBSCBSTot ausente.
    // Severidade faseada por CRT (como IBSCBS_MISSING): FATAL p/ Regime Normal
    // (produção 03/08/2026), WARNING p/ Simples/MEI (04/01/2027).
    if (itemIbscbsBlocks.length > 0 && !ibscbsTot) {
      const evId = makeEvidenceId("IBSCBSTOT_MISSING");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_IBSCBSTOT_MISSING",
          severity: ibsCbsMissingSev,
          ruleId: "IBSCBSTOT_MISSING",
          title: "Grupo de totais IBSCBSTot (W03) ausente — itens informam IBS/CBS",
          field: "IBSCBSTot",
          xpath: inferXpath("total", docType),
          snippet: "<!-- Grupo <IBSCBSTot> não encontrado em <total> -->",
          evidenceId: evId,
          recommendation:
            "Informar <IBSCBSTot> em <total> com o somatório dos campos de IBS/CBS dos itens " +
            "(vBCIBSCBS, gIBS, gCBS) conforme NT 2025.002." +
            (isSimplesOrMei ? SIMPLES_MEI_NOTE : ""),
        }),
        makeEvidence({ id: evId, type: "xml", label: "IBSCBSTot (W03) — grupo ausente", xpath: inferXpath("total", docType), snippet: "<!-- Grupo <IBSCBSTot> não encontrado em <total> -->" }),
      );
    }

    // W34-10 → Rejeição 1118: IBSCBSTot informado sem nenhum item com IBS/CBS.
    // Inconsistência (não faseamento) — FATAL sempre, como IBSCBS_SPLIT/IBSCBS_TOTAL.
    if (ibscbsTot && itemIbscbsBlocks.length === 0) {
      const evId = makeEvidenceId("IBSCBSTOT_UNDUE");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_IBSCBSTOT_UNDUE",
          severity: "FATAL",
          ruleId: "IBSCBSTOT_UNDUE",
          title: "Grupo IBSCBSTot (W03) informado indevidamente — nenhum item possui IBS/CBS",
          field: "IBSCBSTot",
          xpath: inferXpath("IBSCBSTot", docType),
          snippet: ibscbsTot.snippet,
          evidenceId: evId,
          recommendation:
            "Remover <IBSCBSTot> ou informar o grupo IBSCBS nos itens correspondentes conforme NT 2025.002.",
        }),
        makeEvidence({ id: evId, type: "xml", label: "IBSCBSTot (W03) — informado sem itens IBS/CBS", xpath: inferXpath("IBSCBSTot", docType), snippet: ibscbsTot.snippet }),
      );
    }
  }

  // ── Rule 8: CEST_MISSING — CEST must be present (#275 fase 2) ────────────
  // Regulamento 30/abr/2026 + Convênio ICMS 142/2018: CEST é obrigatório
  // apenas para produtos sujeitos a Substituição Tributária. Cruzamos o NCM
  // declarado contra subset curado (lib/validation/cestNcm.ts):
  //   - NCM em segmento ST conhecido → FATAL (CEST realmente obrigatório)
  //   - NCM fora do subset → ALERT (subset não cobre 100% do Conv. 142)
  if (!cest) {
    const ncmValue = ncm?.value ?? "";
    const stLookup = lookupNcmSt(ncmValue);
    const evId = makeEvidenceId("CEST_MISSING");

    if (stLookup.is_st) {
      const segLabel = stLookup.segments.join(", ");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_CEST_MISSING",
          severity: "FATAL",
          ruleId: "CEST_MISSING",
          title: `CEST obrigatório — NCM ${ncmValue} pertence a segmento ST (${segLabel})`,
          field: "CEST",
          xpath: inferXpath("CEST", docType),
          snippet: "<!-- Tag CEST não encontrada no XML -->",
          evidenceId: evId,
          recommendation: `NCM ${ncmValue} consta no Convênio ICMS 142/2018 (${segLabel}). Informe o CEST correspondente em <prod/CEST>.`,
        }),
        makeEvidence({
          id: evId,
          type: "xml",
          label: `CEST obrigatório (segmento ST: ${segLabel})`,
          xpath: inferXpath("CEST", docType),
          snippet: "<!-- Tag CEST não encontrada no XML -->",
        }),
      );
    } else {
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_CEST_MISSING",
          severity: "ALERT",
          ruleId: "CEST_MISSING",
          title: "CEST ausente — verificar se produto é sujeito à substituição tributária",
          field: "CEST",
          xpath: inferXpath("CEST", docType),
          snippet: "<!-- Tag CEST não encontrada no XML -->",
          evidenceId: evId,
          recommendation: `NCM ${ncmValue || "(não informado)"} não consta no subset ST conhecido (Convênio ICMS 142/2018). Se for sujeito a ST, informe o CEST; caso contrário, este aviso pode ser desconsiderado.`,
        }),
        makeEvidence({ id: evId, type: "xml", label: "CEST — ausente (verificar ST)", xpath: inferXpath("CEST", docType), snippet: "<!-- Tag CEST não encontrada no XML -->" }),
      );
    }
  }

  // ── Rule 9b: SPLIT_PAYMENT_INDPAG (#276) ─────────────────────────────────
  // Regulamento IBS cap. 5: indPag=3 (Pix/TED) ou 4 (cartão) sujeito a split
  // payment automático → CBS/IBS devem ser lançados, exceto CSTs sem tributo.
  if (indPag && (indPag.value === "3" || indPag.value === "4")) {
    const cstValue = firstTag(xml, ["CST"])?.value ?? "";
    const vCbsNum = parseFloat(vCBS?.value ?? "0") || 0;
    const vIbsNum = parseFloat(vIBS?.value ?? "0") || 0;
    if (vCbsNum + vIbsNum === 0 && !NO_TAX_CSTS.has(cstValue)) {
      const method = indPag.value === "3" ? "Pix/TED" : "cartão";
      const evId = makeEvidenceId("SPLIT_PAYMENT_INDPAG");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_SPLIT_PAYMENT_INDPAG",
          severity: "FATAL",
          ruleId: "SPLIT_PAYMENT_INDPAG",
          title: `Pagamento via ${method} sujeito a split payment sem CBS/IBS lançados`,
          field: "indPag",
          xpath: inferXpath("indPag", docType),
          snippet: indPag.snippet,
          evidenceId: evId,
          recommendation: `indPag=${indPag.value} (${method}) está sujeito a split payment automático (Regulamento IBS cap. 5), mas a NF-e não lança CBS nem IBS. Confirme se o CST ${cstValue || "(ausente)"} é apropriado ou ajuste vCBS/vIBS.`,
        }),
        makeEvidence({
          id: evId,
          type: "xml",
          label: `Split payment sem tributo (indPag=${indPag.value})`,
          xpath: inferXpath("indPag", docType),
          snippet: indPag.snippet,
        }),
      );
    }
  }

  // ── Rule: IMPORT_IBSCBS_REQUIRED — incidência na importação (#item2) ──────
  // Decreto 12.955/2026 art. 65 (CBS) + Resolução CGIBS nº 6/2026 art. 65 (IBS)
  // — mesmo número de artigo nos dois regulamentos, publicados juntos em
  // 30/04/2026 (LC 214 art. 63): IBS/CBS incidem sobre a importação de bens e
  // serviços independentemente de o importador ser habitual.
  // Detecção: CFOP iniciando em "3" (entrada do exterior) OU grupo de importação
  // (<DI>/<DUIMP>). Export (CFOP 7xxx, imune) e internas ficam de fora.
  // Escopo: grupo IBSCBS presente porém zerado com CST tributável — o grupo ausente
  // já é coberto por IBSCBS_MISSING (evita duplo apontamento).
  if (hasIbscbsGroup && ibscbsBlock) {
    const isImport =
      allTags(xml, "CFOP").some((c) => c.value.trim().startsWith("3")) ||
      /<DI(?=[\s>])/i.test(xml) ||
      /<DUIMP(?=[\s>])/i.test(xml);
    const cstValue = cst?.value ?? "";
    const vCbsNum = parseFloat(vCBS?.value ?? "0") || 0;
    const vIbsNum = parseFloat(vIBS?.value ?? "0") || 0;
    if (isImport && vCbsNum + vIbsNum === 0 && !NO_TAX_CSTS.has(cstValue)) {
      const evId = makeEvidenceId("IMPORT_IBSCBS_REQUIRED");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_IMPORT_IBSCBS_REQUIRED",
          severity: "FATAL",
          ruleId: "IMPORT_IBSCBS_REQUIRED",
          title: "Importação tributável sem IBS/CBS destacado — incidência obrigatória",
          field: "IBS/CBS",
          xpath: inferXpath("IBSCBS", docType),
          snippet: ibscbsBlock.snippet,
          evidenceId: evId,
          recommendation:
            `Operação de importação (CFOP 3xxx ou grupo DI/DUIMP) com IBS/CBS zerado e ` +
            `CST ${cstValue || "(ausente)"} tributável. O IBS e a CBS incidem sobre a importação ` +
            `de bens e serviços independentemente de o importador ser habitual ` +
            `(Decreto 12.955/2026 art. 65 para CBS + Resolução CGIBS nº 6/2026 art. 65 ` +
            `para IBS — mesmo artigo nos dois regulamentos; LC 214 art. 63). A alíquota deve corresponder à da ` +
            `operação interna com o mesmo bem/serviço (art. 469-470). Informe vCBS/vIBS ou ajuste o CST.`,
        }),
        makeEvidence({ id: evId, type: "xml", label: "Importação — IBS/CBS ausente", xpath: inferXpath("IBSCBS", docType), snippet: ibscbsBlock.snippet }),
      );
    }
  }

  // ── Rule: PF_CONTRIB_CNPJ — PF contribuinte deve se inscrever no CNPJ (#item3) ──
  // Comunicado Conjunto CGIBS/RFB nº 01/2025 + LC 214 art. 251 previam 01/07/2026;
  // o Decreto 13.075/2026 (altera o Decreto 12.955/2026, art. 239) adiou para
  // 01/01/2027 a PF contribuinte de IBS/CBS ter CNPJ (emissão por CPF não é
  // permitida a partir daí). Verificável do XML: emitente identificado por CPF +
  // data ≥ 01/01/2027. O enquadramento como contribuinte não é verificável →
  // ALERT informativo.
  {
    const emitBlock = firstTag(xml, ["emit", "PrestadorServico", "prest", "Prestador"]);
    const emDate = emissionDate?.value?.slice(0, 10) ?? "";
    const dateOk = /^\d{4}-\d{2}-\d{2}$/.test(emDate) && emDate >= PF_CNPJ_REQUIRED_DATE;
    if (emitBlock && dateOk) {
      const emitCpf = firstTag(emitBlock.snippet, ["CPF"]);
      const emitCnpj = firstTag(emitBlock.snippet, ["CNPJ"]);
      if (emitCpf && !emitCnpj) {
        const evId = makeEvidenceId("PF_CONTRIB_CNPJ");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_PF_CONTRIB_CNPJ",
            severity: "ALERT",
            ruleId: "PF_CONTRIB_CNPJ",
            title: "Emitente pessoa física (CPF) — verificar obrigação de inscrição no CNPJ",
            field: "emit/CPF",
            xpath: inferXpath("CPF", docType),
            snippet: emitCpf.snippet,
            evidenceId: evId,
            recommendation:
              `Emitente identificado por CPF. A partir de 01/01/2027 (Decreto 13.075/2026, ` +
              `que alterou o Decreto 12.955/2026 art. 239 e adiou o prazo original do ` +
              `Comunicado Conjunto CGIBS/RFB nº 01/2025), a pessoa física contribuinte de ` +
              `IBS/CBS deve se inscrever no CNPJ e não pode emitir documento fiscal por CPF ` +
              `(LC 214 art. 251). Verifique o enquadramento como contribuinte (atividade ` +
              `econômica habitual; locação com mais de 3 imóveis e renda anual acima de ` +
              `R$ 240 mil) e, se for o caso, providencie a inscrição no CNPJ. A inscrição ` +
              `não transforma a PF em PJ.`,
          }),
          makeEvidence({ id: evId, type: "xml", label: "Emitente PF (CPF) — verificar CNPJ", xpath: inferXpath("CPF", docType), snippet: emitCpf.snippet }),
        );
      }
    }
  }

  // ── Rule: DEVOLUCAO_DFEREF — devolução referencia a nota original por item (#312) ──
  // v1.40: NF-e de devolução (finNFe=4) deve referenciar a nota original POR ITEM,
  // exclusivamente via grupo DFeReferenciado. Antes de 01/09/2026 → WARNING (antecipação);
  // a partir da vigência → FATAL. pedagogicalMode mantém WARNING.
  if (isNfe) {
    const fin = firstTag(xml, ["finNFe"]);
    if (fin && fin.value.trim() === "4") {
      const nItems = (xml.match(/<det\b/g) ?? []).length;
      const nRef = (xml.match(/<DFeReferenciado\b/g) ?? []).length;
      if (nRef < Math.max(nItems, 1)) {
        const emDate = emissionDate?.value?.slice(0, 10) ?? "";
        const vigente = /^\d{4}-\d{2}-\d{2}$/.test(emDate) && emDate >= DEVOLUCAO_DFEREF_DATE;
        const sev: FindingSeverity = vigente && !pedMode ? "FATAL" : "WARNING";
        const falta = nRef === 0 ? "nenhum item referencia" : `só ${nRef} de ${nItems} itens referenciam`;
        const evId = makeEvidenceId("DEVOLUCAO_DFEREF");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_DEVOLUCAO_DFEREF",
            severity: sev,
            ruleId: "DEVOLUCAO_DFEREF",
            title: `NF-e de devolução sem DFeReferenciado por item (${falta} a nota original)`,
            field: "DFeReferenciado",
            xpath: inferXpath("DFeReferenciado", docType),
            snippet: fin.snippet,
            evidenceId: evId,
            recommendation:
              "NF-e de devolução (finNFe=4) deve referenciar a nota original POR ITEM, " +
              "exclusivamente via grupo DFeReferenciado (NT 2025.002-RTC v1.40, vigência 01/09/2026). " +
              "Inclua um DFeReferenciado para cada item devolvido. SEFAZ: Rejeição 321 (regras VC02-14 / VC03-20).",
          }),
          makeEvidence({ id: evId, type: "xml", label: "Devolução sem DFeReferenciado por item", xpath: inferXpath("DFeReferenciado", docType), snippet: fin.snippet }),
        );
      }
    }
  }

  // ── Rule: IS_CALC — coerência do Imposto Seletivo declarado (#314) ──────
  // vIS = vBCIS × pIS (ad valorem) + qTrib × pISEspec (específico). Tags exclusivas do IS
  // (sem colisão com o PIS legado vPIS/pPIS). O IS só é cobrado a partir de 2027, mas a
  // coerência do grupo, quando declarado, é validável já.
  const isMatch = xml.match(/<IS\b[^>]*>([\s\S]*?)<\/IS>/);
  if (isNfe && isMatch) {
    const isblk = isMatch[1];
    const isf = (tag: string): number => parseFloat(firstTag(isblk, [tag])?.value ?? "0") || 0;
    const visTag = firstTag(isblk, ["vIS"]);
    if (visTag) {
      const expected = Math.round((isf("vBCIS") * isf("pIS") + isf("qTrib") * isf("pISEspec")) * 100) / 100;
      const declared = parseFloat(visTag.value) || 0;
      if (Math.abs(declared - expected) > 0.01) {
        const evId = makeEvidenceId("IS_CALC");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_IS_CALC",
            severity: "FATAL",
            ruleId: "IS_CALC",
            title: `Imposto Seletivo incoerente: vIS=${declared} declarado, esperado ${expected}`,
            field: "vIS",
            xpath: inferXpath("vIS", docType),
            snippet: visTag.snippet,
            evidenceId: evId,
            recommendation:
              "vIS deve ser vBCIS × pIS (ad valorem) + qTrib × pISEspec (específico), " +
              "conforme NT 2025.002-RTC. Ajuste a base, a alíquota ou o valor do IS.",
          }),
          makeEvidence({ id: evId, type: "xml", label: "IS — cálculo incoerente", xpath: inferXpath("vIS", docType), snippet: visTag.snippet }),
        );
      }
    }
  }

  // ── Rule: IS_EXPECTED — NCM de capítulo sujeito ao IS sem grupo IS (#314) ──
  // Núcleo inequívoco do IS na LC 214: bebidas (cap. 22) e fumo (cap. 24). ALERT informativo
  // (não FATAL): o IS só passa a ser cobrado em 2027 e há exceções.
  if (isNfe && ncm && /^\d{8}$/.test(ncm.value) && !isMatch) {
    const cap = ncm.value.slice(0, 2);
    if (cap === "22" || cap === "24") {
      const evId = makeEvidenceId("IS_EXPECTED");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_IS_EXPECTED",
          severity: "ALERT",
          ruleId: "IS_EXPECTED",
          title: `NCM ${ncm.value} pode estar sujeito ao Imposto Seletivo — grupo IS ausente`,
          field: "IS",
          xpath: inferXpath("IS", docType),
          snippet: ncm.snippet,
          evidenceId: evId,
          recommendation:
            "Produtos dos capítulos 22 (bebidas) e 24 (fumo) são, em regra, sujeitos ao " +
            "Imposto Seletivo (LC 214 art. 409). A cobrança do IS inicia em 2027; verifique " +
            "o enquadramento e, quando aplicável, informe o grupo IS na NF-e.",
        }),
        makeEvidence({ id: evId, type: "xml", label: "IS — NCM possivelmente sujeito, grupo ausente", xpath: inferXpath("IS", docType), snippet: ncm.snippet }),
      );
    }
  }

  // ── Rule: SUFRAMA_DV — DV da Inscrição SUFRAMA do emitente (#311, C22-20) ──
  if (isNfe) {
    const isuf = firstTag(xml, ["ISUFemit", "ISUF"]);
    if (isuf && isuf.value.trim() && !suframaDvOk(isuf.value)) {
      const evId = makeEvidenceId("SUFRAMA_DV");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_SUFRAMA_DV",
          severity: "WARNING",
          ruleId: "SUFRAMA_DV",
          title: `Inscrição SUFRAMA "${isuf.value.trim()}" — dígito verificador inválido`,
          field: "ISUFemit",
          xpath: inferXpath("ISUFemit", docType),
          snippet: isuf.snippet,
          evidenceId: evId,
          recommendation:
            "A Inscrição SUFRAMA do emitente deve ter 9 dígitos com DV válido (módulo 11). " +
            "Verifique a inscrição. SEFAZ: Rejeição C22-20 (DV da Inscrição SUFRAMA do emitente inválido).",
        }),
        makeEvidence({ id: evId, type: "xml", label: "SUFRAMA — DV inválido", xpath: inferXpath("ISUFemit", docType), snippet: isuf.snippet }),
      );
    }
  }

  // ── Rule: ALCZFM_NPROC — grupo gALCZFMCBS exige nProcSuframa (#311, UB66c-10) ──
  if (isNfe) {
    const alc = xml.match(/<gALCZFMCBS\b[^>]*>([\s\S]*?)<\/gALCZFMCBS>/i);
    if (alc) {
      const nproc = firstTag(alc[1], ["nProcSuframa"]);
      if (!(nproc && nproc.value.trim())) {
        const evId = makeEvidenceId("ALCZFM_NPROC");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_ALCZFM_NPROC",
            severity: "WARNING",
            ruleId: "ALCZFM_NPROC",
            title: "Grupo ALC/ZFM (gALCZFMCBS) sem nProcSuframa",
            field: "nProcSuframa",
            xpath: inferXpath("nProcSuframa", docType),
            snippet: alc[0].slice(0, 200),
            evidenceId: evId,
            recommendation:
              "Operações com benefício de ALC/Zona Franca (grupo gALCZFMCBS) exigem o número do processo na " +
              "SUFRAMA (nProcSuframa) do processo produtivo aprovado. Informe o nProcSuframa. SEFAZ: Rejeição 1192 (regra UB66c-10).",
          }),
          makeEvidence({ id: evId, type: "xml", label: "ALC/ZFM — nProcSuframa ausente", xpath: inferXpath("nProcSuframa", docType), snippet: alc[0].slice(0, 200) }),
        );
      }
    }
  }

  // ── Rule: CINDOP_NFCE — cIndOp não é permitido na NFC-e (#311, B25d) ──
  if (docType === "NFCE") {
    const cindop = firstTag(xml, ["cIndOp"]);
    if (cindop && cindop.value.trim()) {
      const evId = makeEvidenceId("CINDOP_NFCE");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_CINDOP_NFCE",
          severity: "WARNING",
          ruleId: "CINDOP_NFCE",
          title: "cIndOp informado em NFC-e (modelo 65) — não permitido",
          field: "cIndOp",
          xpath: inferXpath("cIndOp", docType),
          snippet: cindop.snippet,
          evidenceId: evId,
          recommendation:
            "O campo cIndOp (Código Indicador do Local da Operação de Fornecimento) não é permitido na " +
            "NFC-e (modelo 65) — remova-o. SEFAZ: Rejeição 1099 (regra B25d-10).",
        }),
        makeEvidence({ id: evId, type: "xml", label: "cIndOp — não permitido em NFC-e", xpath: inferXpath("cIndOp", docType), snippet: cindop.snippet }),
      );
    }
  }

  // ── Rule: RETIRADA_CINDOP — B25d-30: cIndOp 010104/010105 exige Local de Retirada (#311) ──
  if (docType === "NFE") {
    const cind = firstTag(xml, ["cIndOp"]);
    const v = cind?.value.trim();
    if (cind && (v === "010104" || v === "010105") && !/<retirada(?=[\s>])/i.test(xml)) {
      const evId = makeEvidenceId("RETIRADA_CINDOP");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_RETIRADA_CINDOP",
          severity: "WARNING",
          ruleId: "RETIRADA_CINDOP",
          title: `cIndOp ${v} exige o grupo Local de Retirada (ausente)`,
          field: "retirada",
          xpath: inferXpath("retirada", docType),
          snippet: cind.snippet,
          evidenceId: evId,
          recommendation:
            "cIndOp 010104 (leilão/licitação) ou 010105 (irregularidade) exige o grupo Local de Retirada " +
            "(retirada) informado. SEFAZ: Rejeição 1110 (regra B25d-30).",
        }),
        makeEvidence({ id: evId, type: "xml", label: "Local de Retirada ausente (cIndOp 010104/010105)", xpath: inferXpath("retirada", docType), snippet: cind.snippet }),
      );
    }
  }

  // ── Rule: ALCZFM_CBS_CALC — UB66e-10: vTribRegCBS = vBC × pAliqEfetRegCBS/100 (#311) ──
  {
    const alc = xml.match(/<gALCZFMCBS\b[^>]*>([\s\S]*?)<\/gALCZFMCBS>/i);
    if (isNfe && alc) {
      const vtrib = firstTag(alc[1], ["vTribRegCBS"]);
      const palq = firstTag(alc[1], ["pAliqEfetRegCBS"]);
      const vbc = firstTag(xml, ["vBC"]);
      if (vtrib && palq && vbc) {
        const exp = Math.round((parseFloat(vbc.value) * parseFloat(palq.value)) / 100 * 100) / 100;
        const decl = parseFloat(vtrib.value) || 0;
        if (Math.abs(decl - exp) > 0.01) {
          const evId = makeEvidenceId("ALCZFM_CBS_CALC");
          pushFindingAndEvidence(findings, evidences, evidenceById,
            makeFinding({
              id: "F_ALCZFM_CBS_CALC",
              severity: "WARNING",
              ruleId: "ALCZFM_CBS_CALC",
              title: `vTribRegCBS (${decl}) diverge do calculado (${exp}) na operação ALC/ZFM`,
              field: "vTribRegCBS",
              xpath: inferXpath("vTribRegCBS", docType),
              snippet: vtrib.snippet,
              evidenceId: evId,
              recommendation:
                "Em operação ALC/ZFM, vTribRegCBS deve ser vBC × (pAliqEfetRegCBS / 100). " +
                "Ajuste o valor. SEFAZ: Rejeição 1218 (regra UB66e-10).",
            }),
            makeEvidence({ id: evId, type: "xml", label: "ALC/ZFM — vTribRegCBS incoerente", xpath: inferXpath("vTribRegCBS", docType), snippet: vtrib.snippet }),
          );
        }
      }
    }
  }

  // ── Rule: DANFE_SIMPLIFICADO_RESTRICAO — restrições do DANFE Simplificado Tipo 2 (NT 2026.002 v1.00, #405) ──
  // tpImp=6 (modelo 55 apenas — Ajuste SINIEF 13/2026) restringe a nota a: saída
  // (tpNF≠0), operação interna (idDest=1), sem NFref e finalidade Normal (finNFe=1).
  // 4 restrições confirmadas com código de rejeição oficial e convergência de fontes
  // independentes. Allowlist de CFOP (5ª restrição) coberta por DANFE_SIMPLIFICADO_CFOP,
  // abaixo (#482). Fora de escopo: o grupo de alerta cStat=120/PR13 (vive no protocolo
  // de autorização da SEFAZ, não no XML emitido — fora do que este validador processa).
  if (docType === "NFE") {
    const tpImp = firstTag(xml, ["tpImp"]);
    if (tpImp && tpImp.value.trim() === "6") {
      const emDate = emissionDate?.value?.slice(0, 10) ?? "";
      const vigente = /^\d{4}-\d{2}-\d{2}$/.test(emDate) && emDate >= DANFE_T2_PRODUCAO_DATE;
      const sev: FindingSeverity = vigente && !pedMode ? "FATAL" : "WARNING";

      const tpNf = firstTag(xml, ["tpNF"]);
      if (tpNf && tpNf.value.trim() === "0") {
        const evId = makeEvidenceId("DANFE_T2_ENTRADA");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_DANFE_T2_ENTRADA",
            severity: sev,
            ruleId: "DANFE_SIMPLIFICADO_RESTRICAO",
            title: "DANFE Simplificado Tipo 2 (tpImp=6) não é admitido em operação de entrada (tpNF=0)",
            field: "tpNF",
            xpath: inferXpath("tpNF", docType),
            snippet: tpNf.snippet,
            evidenceId: evId,
            recommendation:
              "O DANFE Simplificado Tipo 2 (Ajuste SINIEF 13/2026) só é admitido em operações de saída. " +
              "Corrija tpNF ou remova tpImp=6. SEFAZ: Rejeição 706 (regra B11-10).",
          }),
          makeEvidence({ id: evId, type: "xml", label: "DANFE T2 — operação de entrada não permitida", xpath: inferXpath("tpNF", docType), snippet: tpNf.snippet }),
        );
      }

      const idDest = firstTag(xml, ["idDest"]);
      if (idDest && idDest.value.trim() !== "1") {
        const evId = makeEvidenceId("DANFE_T2_INTERESTADUAL");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_DANFE_T2_INTERESTADUAL",
            severity: sev,
            ruleId: "DANFE_SIMPLIFICADO_RESTRICAO",
            title: "DANFE Simplificado Tipo 2 (tpImp=6) não é admitido em operação interestadual/exterior (idDest≠1)",
            field: "idDest",
            xpath: inferXpath("idDest", docType),
            snippet: idDest.snippet,
            evidenceId: evId,
            recommendation:
              "O DANFE Simplificado Tipo 2 só é admitido em operações internas (idDest=1). " +
              "Corrija idDest ou remova tpImp=6. SEFAZ: Rejeição 707 (regra B11a-10).",
          }),
          makeEvidence({ id: evId, type: "xml", label: "DANFE T2 — operação interestadual/exterior não permitida", xpath: inferXpath("idDest", docType), snippet: idDest.snippet }),
        );
      }

      if (/<NFref(?=[\s>])/i.test(xml)) {
        const evId = makeEvidenceId("DANFE_T2_NFREF");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_DANFE_T2_NFREF",
            severity: sev,
            ruleId: "DANFE_SIMPLIFICADO_RESTRICAO",
            title: "DANFE Simplificado Tipo 2 (tpImp=6) não pode referenciar outro documento fiscal (NFref)",
            field: "NFref",
            xpath: inferXpath("NFref", docType),
            snippet: tpImp.snippet,
            evidenceId: evId,
            recommendation:
              "O DANFE Simplificado Tipo 2 não admite o grupo NFref (referência a outro documento fiscal). " +
              "Remova o NFref ou o tpImp=6. SEFAZ: Rejeição 708 (regra BA01-10).",
          }),
          makeEvidence({ id: evId, type: "xml", label: "DANFE T2 — referência a documento fiscal não permitida", xpath: inferXpath("NFref", docType), snippet: tpImp.snippet }),
        );
      }

      const finT2 = firstTag(xml, ["finNFe"]);
      if (finT2 && finT2.value.trim() !== "1") {
        const evId = makeEvidenceId("DANFE_T2_FINALIDADE");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_DANFE_T2_FINALIDADE",
            severity: sev,
            ruleId: "DANFE_SIMPLIFICADO_RESTRICAO",
            title: "DANFE Simplificado Tipo 2 (tpImp=6) exige finalidade Normal (finNFe=1)",
            field: "finNFe",
            xpath: inferXpath("finNFe", docType),
            snippet: finT2.snippet,
            evidenceId: evId,
            recommendation:
              "O DANFE Simplificado Tipo 2 só é admitido com finalidade Normal (finNFe=1). " +
              "Corrija finNFe ou remova tpImp=6. SEFAZ: Rejeição 715 (regra B25-20).",
          }),
          makeEvidence({ id: evId, type: "xml", label: "DANFE T2 — finalidade não permitida", xpath: inferXpath("finNFe", docType), snippet: finT2.snippet }),
        );
      }

      // ── Rule: DANFE_SIMPLIFICADO_CFOP — allowlist de CFOP (NT 2026.002 v1.00, #482) ──
      // Regra I08-150 — Rejeição 725 (mesmo código já usado pela SEFAZ para "NFC-e com
      // CFOP inválido", reaproveitado para NF-e+tpImp=6 — DANFE Simplificado Tipo 2
      // estende a mesma semântica de venda direta ao consumidor da NFC-e ao NF-e mod. 55).
      // Confirmado por 2 fontes independentes (fórum SPED Brasil + doc. Senior listando
      // I08-150 entre as regras da NT 2026.002 v1.00) + a lista de CFOPs bate quase 1:1
      // com a lista já documentada da Rejeição 725 de NFC-e (mesma fonte, +1 código: 5910).
      const cfopAllowlist = new Set(["5101", "5102", "5103", "5104", "5115", "5405", "5656", "5667", "5910", "5933"]);
      const badCfop = allTags(xml, "CFOP").find((c) => !cfopAllowlist.has(c.value.trim()));
      if (badCfop) {
        const evId = makeEvidenceId("DANFE_T2_CFOP");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_DANFE_T2_CFOP",
            severity: sev,
            ruleId: "DANFE_SIMPLIFICADO_CFOP",
            title: `DANFE Simplificado Tipo 2 (tpImp=6) não admite CFOP ${badCfop.value} — fora do allowlist de venda direta ao consumidor`,
            field: "CFOP",
            xpath: inferXpath("CFOP", docType),
            snippet: badCfop.snippet,
            evidenceId: evId,
            recommendation:
              "O DANFE Simplificado Tipo 2 só admite CFOPs de venda direta ao consumidor: 5101, 5102, 5103, " +
              "5104, 5115, 5405, 5656, 5667, 5910, 5933. Corrija o CFOP do item ou remova tpImp=6. " +
              "SEFAZ: Rejeição 725 (regra I08-150).",
          }),
          makeEvidence({ id: evId, type: "xml", label: "DANFE T2 — CFOP fora do allowlist", xpath: inferXpath("CFOP", docType), snippet: badCfop.snippet }),
        );
      }
    }
  }

  // ── Rule: INDZFMALC_CBS_ZERO — indZFMALC ativo exige CBS zero (NFS-e, NT 007/2026, #406) ──
  // indZFMALC sinaliza operação sob benefício de alíquota zero de CBS (ZFM/ALC, LC
  // 214/2025). WARNING: a própria plataforma nacional NFS-e ainda não valida este
  // campo (preenchimento com validação desativada) — nosso valor é sinalizar o que
  // a plataforma ainda não sinaliza, não reproduzir rejeição dura.
  if (docType === "NFSE" && indZfmalc && /^(1|true|s|sim)$/i.test(indZfmalc.value.trim())) {
    const zfmalcCbs = hasIbscbsGroup ? vCBS : valorCbs;
    if (zfmalcCbs) {
      const val = parseFloat(zfmalcCbs.value) || 0;
      if (val > 0.01) {
        const evId = makeEvidenceId("INDZFMALC_CBS_ZERO");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_INDZFMALC_CBS_ZERO",
            severity: "WARNING",
            ruleId: "INDZFMALC_CBS_ZERO",
            title: `indZFMALC ativo, mas CBS = R$ ${val.toFixed(2)} (esperado zero)`,
            field: zfmalcCbs.tag,
            xpath: inferXpath(zfmalcCbs.tag, docType),
            snippet: zfmalcCbs.snippet,
            evidenceId: evId,
            recommendation:
              "indZFMALC indica operação com benefício de alíquota zero de CBS (Zona Franca de Manaus/Área " +
              "de Livre Comércio, LC 214/2025). Com o indicador ativo, o valor de CBS deve ser zero. " +
              "NT 007/2026 (SE/CGNFS-e) — validação ainda desativada na plataforma nacional; checagem preventiva do Tribultz.",
          }),
          makeEvidence({ id: evId, type: "xml", label: "indZFMALC × CBS incoerente", xpath: inferXpath(zfmalcCbs.tag, docType), snippet: zfmalcCbs.snippet }),
        );
      }
    }
  }

  // ── Rule: PIS_COFINS_DEVIDO_NEGATIVO — vPis/vCofins devidos não podem ser < 0 (NT 007/2026, #406) ──
  // A partir da NT 007/2026, vPis/vCofins informam apenas o valor DEVIDO (não mais
  // retido) — um valor devido negativo é logicamente incoerente. Checagem de formato
  // mínima, independente da checagem de valor exato (PIS_COFINS_DEVIDO_CALC, #480).
  for (const [tagResult, label, fid] of [
    [vPis, "vPis", "PIS_COFINS_DEVIDO_NEGATIVO_PIS"],
    [vCofins, "vCofins", "PIS_COFINS_DEVIDO_NEGATIVO_COFINS"],
  ] as const) {
    if (tagResult) {
      const val = parseFloat(tagResult.value);
      if (!Number.isNaN(val) && val < 0) {
        const evId = makeEvidenceId(fid);
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: `F_${fid}`,
            severity: "WARNING",
            ruleId: "PIS_COFINS_DEVIDO_NEGATIVO",
            title: `${label} negativo (R$ ${val.toFixed(2)}) — a partir da NT 007/2026 informa valor devido, não retenção`,
            field: tagResult.tag,
            xpath: inferXpath(tagResult.tag, docType),
            snippet: tagResult.snippet,
            evidenceId: evId,
            recommendation:
              `${label} passou a informar apenas o valor DEVIDO (NT 007/2026, SE/CGNFS-e) — um valor devido ` +
              "não pode ser negativo. Se o XML ainda trata este campo como retenção (semântica anterior), corrija para o valor devido.",
          }),
          makeEvidence({ id: evId, type: "xml", label: `${label} — valor devido negativo`, xpath: inferXpath(tagResult.tag, docType), snippet: tagResult.snippet }),
        );
      }
    }
  }

  // ── Rule: PIS_COFINS_DEVIDO_CALC — vPis/vCofins = base × alíquota (NT 007/2026, #480) ──
  // Fórmula confirmada por fonte verificável (não especulada): a NT 007/2026
  // (SE/CGNFS-e, 07/02/2026) atualiza o grupo "piscofins" (CST + tpRetPisCofins),
  // mas não altera os campos pré-existentes vBCPisCofins/pAliqPis/pAliqCofins —
  // confirmados via manual de integração NFS-e pós-NT007 e corroborados de forma
  // independente (FocusNFe). Exemplo oficial: vBCPisCofins=988.33, pAliqPis=1.65
  // (%) → vPis=16.31 (988.33 × 1.65 / 100, arredondamento bancário) — bate exato.
  // Alíquotas em formato percentual (1.65 = 1,65%), não fração — por isso ÷100,
  // ao contrário de IBSCBS_CALC (que usa fração). Tolerância R$0,01 (oficial).
  // Campos opcionais — regra só dispara quando base e alíquota estão presentes
  // (mesma degradação graciosa do IBSCBS_CALC). WARNING: a plataforma nacional
  // NFS-e ainda não valida estes campos.
  for (const [aliq, declared, label, fid] of [
    [aliquotaPis, vPis, "vPis", "PIS_COFINS_DEVIDO_CALC_PIS"],
    [aliquotaCofins, vCofins, "vCofins", "PIS_COFINS_DEVIDO_CALC_COFINS"],
  ] as const) {
    if (baseCalculoPisCofins && aliq && declared) {
      const base = parseFloat(baseCalculoPisCofins.value);
      const rate = parseFloat(aliq.value);
      const val = parseFloat(declared.value);
      if (!Number.isNaN(base) && !Number.isNaN(rate) && !Number.isNaN(val)) {
        const expected = (base * rate) / 100;
        if (Math.abs(val - expected) > 0.01) {
          const evId = makeEvidenceId(fid);
          pushFindingAndEvidence(findings, evidences, evidenceById,
            makeFinding({
              id: `F_${fid}`,
              severity: "WARNING",
              ruleId: "PIS_COFINS_DEVIDO_CALC",
              title: `${label} incorreto — informado R$ ${val.toFixed(2)}, esperado R$ ${expected.toFixed(2)}`,
              field: declared.tag,
              xpath: inferXpath(declared.tag, docType),
              snippet: declared.snippet,
              evidenceId: evId,
              recommendation:
                `${label} deve ser base de cálculo (R$ ${base.toFixed(2)}) × alíquota (${rate.toFixed(2)}%) = R$ ${expected.toFixed(2)} ` +
                "(NT 007/2026, tolerância R$ 0,01, arredondamento bancário). Validação ainda desativada na plataforma nacional NFS-e.",
            }),
            makeEvidence({ id: evId, type: "xml", label: `${label} — cálculo divergente`, xpath: inferXpath(declared.tag, docType), snippet: declared.snippet }),
          );
        }
      }
    }
  }

  // ── Rule 9: CEST_FORMAT — CEST must be exactly 7 digits ──────────────────

  if (cest && !/^\d{7}$/.test(cest.value)) {
    const evId = makeEvidenceId("CEST_FORMAT");
    pushFindingAndEvidence(findings, evidences, evidenceById,
      makeFinding({
        id: "F_CEST_FORMAT",
        severity: "FATAL",
        ruleId: "CEST_FORMAT",
        title: `CEST inválido (esperado 7 dígitos, encontrado "${cest.value}")`,
        field: "CEST",
        xpath: inferXpath(cest.tag, docType),
        snippet: cest.snippet,
        evidenceId: evId,
        recommendation: "CEST deve ter exatamente 7 dígitos no formato novo. Verificar código atualizado.",
      }),
      makeEvidence({ id: evId, type: "xml", label: "CEST — formato inválido", xpath: inferXpath(cest.tag, docType), snippet: cest.snippet }),
    );
  }

  // ── Rule 10: LAYOUT_PORTAL — required structure (NFS-e only) ─────────────

  if (!isNfe) {
    const requiredLayoutTags = ["Valores", "PrestadorServico", "TomadorServico"] as const;
    const missingLayout = requiredLayoutTags.filter((tag) => !firstTag(xml, [tag]));
    if (missingLayout.length > 0) {
      const evId = makeEvidenceId("LAYOUT_PORTAL");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_LAYOUT_PORTAL",
          severity: "FATAL",
          ruleId: "LAYOUT_PORTAL",
          title: `Layout fora do padrão Portal Nacional — faltam: ${missingLayout.join(", ")}`,
          field: "Estrutura XML",
          xpath: inferXpath("infNfse", docType),
          snippet: `<!-- Tags obrigatórias ausentes: ${missingLayout.join(", ")} -->`,
          evidenceId: evId,
          recommendation: "Documento deve seguir layout do Portal Nacional de NFS-e com todas as seções obrigatórias.",
        }),
        makeEvidence({ id: evId, type: "xml", label: "Layout — tags obrigatórias ausentes", xpath: inferXpath("infNfse", docType), snippet: `<!-- Tags obrigatórias ausentes: ${missingLayout.join(", ")} -->` }),
      );
    }
  }

  // ── Rule 10b: NF-e layout — required structure (NF-e/NFC-e) ──────────────

  if (isNfe) {
    const requiredNfeTags = ["emit", "det", "total"] as const;
    const missingNfe = requiredNfeTags.filter((tag) => !firstTag(xml, [tag]));
    if (missingNfe.length > 0) {
      const evId = makeEvidenceId("LAYOUT_NFE");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_LAYOUT_NFE",
          severity: "FATAL",
          ruleId: "LAYOUT_NFE",
          title: `Estrutura NF-e incompleta — faltam: ${missingNfe.join(", ")}`,
          field: "Estrutura XML",
          xpath: inferXpath("infNFe", docType),
          snippet: `<!-- Tags obrigatórias ausentes: ${missingNfe.join(", ")} -->`,
          evidenceId: evId,
          recommendation: "NF-e deve conter emit, det e total conforme layout padrão.",
        }),
        makeEvidence({ id: evId, type: "xml", label: "NF-e — estrutura incompleta", xpath: inferXpath("infNFe", docType), snippet: `<!-- Tags obrigatórias ausentes: ${missingNfe.join(", ")} -->` }),
      );
    }
  }

  // ── Rules NT 2025.002 V1.36: dPrevEntrega (Cartilha CGIBS item 1.1) ─────────
  // Determina o período de apuração do IBS. Nenhum outro validador cobre essas regras.

  if (isNfe) {
    const freteVal = modFrete?.value ?? "";

    // Rule: DPREV_ENTREGA_FRETE — Rejeição 1157 preventiva
    if (dPrevEntrega && (freteVal === "1" || freteVal === "9")) {
      const evId = makeEvidenceId("DPREV_ENTREGA_FRETE");
      const freteLabel = freteVal === "1" ? "FOB" : "Sem Frete";
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_DPREV_ENTREGA_FRETE",
          severity: "FATAL",
          ruleId: "DPREV_ENTREGA_FRETE",
          title: `Rejeição 1157 — dPrevEntrega inválido para modFrete=${freteVal} (${freteLabel})`,
          field: "dPrevEntrega",
          xpath: inferXpath("dPrevEntrega", docType),
          snippet: dPrevEntrega.snippet,
          evidenceId: evId,
          recommendation:
            `dPrevEntrega é permitido apenas em operações CIF. modFrete=${freteVal} (${freteLabel}) ` +
            "causará Rejeição 1157 no SEFAZ. Remova o campo ou use frete CIF (NT 2025.002 V1.36).",
        }),
        makeEvidence({ id: evId, type: "xml", label: "dPrevEntrega — Rejeição 1157",
          xpath: inferXpath("dPrevEntrega", docType), snippet: dPrevEntrega.snippet }),
      );
    }

    // Rule: DPREV_ENTREGA_COMPETENCIA — divergência contabilização × apuração IBS ⭐
    // Este é o maior diferenciador: nenhum sistema alerta sobre isso.
    if (dPrevEntrega && dhEmi) {
      const dprevMonth = dPrevEntrega.value.slice(0, 7);   // YYYY-MM
      const demiMonth  = dhEmi.value.slice(0, 7);          // YYYY-MM (de YYYY-MM-DDTHH:...)
      if (dprevMonth && demiMonth && dprevMonth !== demiMonth) {
        const evId = makeEvidenceId("DPREV_ENTREGA_COMPETENCIA");
        pushFindingAndEvidence(findings, evidences, evidenceById,
          makeFinding({
            id: "F_DPREV_ENTREGA_COMPETENCIA",
            severity: "ALERT",
            ruleId: "DPREV_ENTREGA_COMPETENCIA",
            title: `Divergência de competência: IBS apurado em ${dprevMonth}, contabilização em ${demiMonth}`,
            field: "dPrevEntrega",
            xpath: inferXpath("dPrevEntrega", docType),
            snippet: dPrevEntrega.snippet,
            evidenceId: evId,
            recommendation:
              `dPrevEntrega (${dprevMonth}) difere do mês de emissão (${demiMonth}). ` +
              `O débito de IBS será apurado em ${dprevMonth} (mês da entrega), mas o ICMS e a ` +
              `contabilização ficam em ${demiMonth} (mês da emissão). ` +
              "Verifique a alíquota vigente na data de entrega e alinhe com o contador. " +
              "Use Evento 112150 para corrigir a data após a emissão (Cartilha CGIBS item 4.12).",
          }),
          makeEvidence({ id: evId, type: "xml", label: "dPrevEntrega — divergência de competência",
            xpath: inferXpath("dPrevEntrega", docType), snippet: dPrevEntrega.snippet }),
        );
      }
    }

    // Rule: DPREV_ENTREGA_CIF_AUSENTE — CIF sem dPrevEntrega
    if (!dPrevEntrega && freteVal === "0") {
      const evId = makeEvidenceId("DPREV_ENTREGA_CIF_AUSENTE");
      pushFindingAndEvidence(findings, evidences, evidenceById,
        makeFinding({
          id: "F_DPREV_ENTREGA_CIF_AUSENTE",
          severity: "ALERT",
          ruleId: "DPREV_ENTREGA_CIF_AUSENTE",
          title: "Operação CIF sem dPrevEntrega — risco de IBS em período incorreto",
          field: "dPrevEntrega",
          xpath: inferXpath("ide", docType),
          evidenceId: evId,
          recommendation:
            "Operação CIF (modFrete=0): o fato gerador do IBS ocorre na entrega ao destinatário. " +
            "Sem dPrevEntrega, o sistema de Apuração Assistida usará a Data de Saída (dhSaiEnt). " +
            "Se a entrega ocorrer em mês diferente, o IBS será lançado no período errado. " +
            "Preencha dPrevEntrega com a data prevista de entrega " +
            "(Cartilha CGIBS item 1.1 + NT 2025.002 V1.36).",
        }),
        makeEvidence({ id: evId, type: "xml", label: "dPrevEntrega — ausente em CIF",
          xpath: inferXpath("ide", docType) }),
      );
    }
  }

  // ── NCM advisory (ALERT) ─────────────────────────────────────────────────

  const ncmEvId = makeEvidenceId("NCM_INFO");
  evidences.push(
    makeEvidence({
      id: ncmEvId,
      type: "xml",
      label: "NCM (avaliação informativa)",
      xpath: ncm ? inferXpath(ncm.tag, docType) : inferXpath("NCM", docType),
      snippet: ncm?.snippet ?? "<!-- NCM não encontrado -->",
    }),
  );
  findings.push(
    makeFinding({
      id: "A_NCM_REVIEW",
      severity: "ALERT",
      ruleId: "NCM_PLACEHOLDER",
      title: "Revisar NCM conforme classificação fiscal vigente",
      field: "NCM",
      xpath: ncm ? inferXpath(ncm.tag, docType) : inferXpath("NCM", docType),
      snippet: ncm?.snippet,
      evidenceId: ncmEvId,
      recommendation: "Conferir classificação fiscal (NCM) e manter evidência de suporte.",
    }),
  );

  const benefitEvId = makeEvidenceId("BENEFITS_INFO");
  evidences.push(
    makeEvidence({
      id: benefitEvId,
      type: "print",
      label: "Checklist de benefícios/créditos",
      snippet: "Validar benefícios e créditos aplicáveis antes do fechamento.",
    }),
  );
  findings.push(
    makeFinding({
      id: "A_BENEFITS_REVIEW",
      severity: "ALERT",
      ruleId: "BENEFITS_PLACEHOLDER",
      title: "Revisar benefícios e créditos aplicáveis",
      field: "beneficios_creditos",
      evidenceId: benefitEvId,
      recommendation: "Documentar justificativa fiscal para benefícios e créditos utilizados.",
    }),
  );

  // ── NT v1.40 — anotar código de rejeição SEFAZ nas detecções (#311) ───────
  // Apenas NF-e/NFC-e (rejeições da SEFAZ NF-e; NFS-e tem regras próprias).
  if (isNfe) {
    for (const f of findings) {
      const code = REJECTION_CODES[f.rule_id];
      if (code) {
        (f as { recommendation: string }).recommendation = (f.recommendation || "") + code;
      }
    }
  }

  // ── Downgrade de obrigações acessórias FATAL → WARNING ────────────────────
  // Duas bases legais independentes e combináveis:
  //  - pedagogicalMode (LC 227/2026 art. 348): flag manual, 60 dias p/ regularizar;
  //  - janela sem penalidades (Ato Conjunto RFB/CGIBS 1/25): automática por dhEmi,
  //    fatos geradores até 31/07/2026.
  const noPenaltyWindow = isWithinNoPenaltyWindow(emissionDate?.value);
  if (pedMode || noPenaltyWindow) {
    for (const f of findings) {
      if (f.severity === "FATAL" && PEDAGOGICAL_ACCESSORY_RULES.has(f.rule_id)) {
        (f as { severity: string }).severity = "WARNING";
        let note = "";
        if (pedMode) note += LC227_NOTE;
        if (noPenaltyWindow) note += ATO_CONJUNTO_NOTE;
        (f as { recommendation: string }).recommendation = (f.recommendation || "") + note;
      }
    }
  }

  // ── Build result ──────────────────────────────────────────────────────────

  const job: ValidationJobRef = {
    id: jobId,
    created_at: nowIso(),
    tenant_id: input.tenantId,
  };
  const audit: ValidationAuditRef = {
    id: auditId,
    job_id: jobId,
    events: [
      {
        id: `evt_${fingerprint}_created`,
        action: "xml_validation_started",
        created_at: nowIso(),
        payload: {
          document_type: docType,
          findings_total: findings.length,
          fatals: findings.filter((f) => f.severity === "FATAL").length,
        },
      },
    ],
  };

  return { job, audit, findings, evidences };
}
