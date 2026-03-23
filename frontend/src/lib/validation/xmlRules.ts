import type {
  Finding,
  FindingSeverity,
  ValidationAuditRef,
  ValidationEvidence,
  ValidationJobRef,
  ValidationResultV11,
  XmlDocumentType,
} from "@/lib/types";

export type ValidationInput = {
  tenantId: string;
  documentType: XmlDocumentType;
  xml: string;
};

// ── CST table (NT 2025.002-RTC) ────────────────────────────────────────────
// Maps valid CST codes to their required XML group and description.

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

  // NFS-e legacy fields
  const serviceCode = firstTag(xml, ["CodigoServico", "cServ", "codigoServico"]);
  const valorCbs = firstTag(xml, ["ValorCBS", "vCBS"]);
  const valorIbs = firstTag(xml, ["ValorIBS", "vIBS"]);
  const aliquotaCbs = firstTag(xml, ["AliquotaCBS", "pCBS"]);
  const aliquotaIbs = firstTag(xml, ["AliquotaIBS", "pIBSUF", "pIBSMun"]);
  const baseCalculo = firstTag(xml, ["BaseCalculo", "vBC"]);

  // NF-e IBSCBS group fields
  const vBC = firstTag(xml, ["vBC"]);
  const pCBS = firstTag(xml, ["pCBS"]);
  const vCBS = firstTag(xml, ["vCBS"]);
  const pIBSUF = firstTag(xml, ["pIBSUF"]);
  const vIBSUF = firstTag(xml, ["vIBSUF"]);
  const pIBSMun = firstTag(xml, ["pIBSMun"]);
  const vIBSMun = firstTag(xml, ["vIBSMun"]);
  const vIBS = firstTag(xml, ["vIBS"]);

  // NF-e totals
  const ibscbsTot = firstTag(xml, ["IBSCBSTot"]);
  const totVIBS = ibscbsTot ? firstTag(ibscbsTot.snippet, ["vIBS"]) : null;
  const totVCBS = ibscbsTot ? firstTag(ibscbsTot.snippet, ["vCBS"]) : null;

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
          severity: "FATAL",
          ruleId: "IBSCBS_MISSING",
          title: "Grupo IBSCBS ausente — obrigatório conforme NT 2025.002",
          field: "IBSCBS",
          xpath: inferXpath("imposto", docType),
          snippet: "<!-- Grupo <IBSCBS> não encontrado em <imposto> -->",
          evidenceId: evId,
          recommendation: "Informar grupo IBSCBS com CST, cClassTrib e campos de cálculo conforme NT 2025.002.",
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
          severity: "FATAL",
          ruleId: "IBSCBS_MISSING",
          title: "IBS/CBS ausentes na nota — obrigatório informar percentual e valor",
          field: "IBS/CBS",
          xpath: inferXpath("Valores", docType),
          snippet: "<!-- Tags ValorCBS, ValorIBS, AliquotaCBS, AliquotaIBS não encontradas -->",
          evidenceId: evId,
          recommendation: "Informar alíquota e valor de IBS (0,90%) e CBS (0,10%) conforme LC 214.",
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

  // ── Rule 8: CEST_MISSING — CEST must be present ──────────────────────────

  if (!cest) {
    const evId = makeEvidenceId("CEST_MISSING");
    pushFindingAndEvidence(findings, evidences, evidenceById,
      makeFinding({
        id: "F_CEST_MISSING",
        severity: "FATAL",
        ruleId: "CEST_MISSING",
        title: "CEST ausente — código obrigatório conforme nova classificação",
        field: "CEST",
        xpath: inferXpath("CEST", docType),
        snippet: "<!-- Tag CEST não encontrada no XML -->",
        evidenceId: evId,
        recommendation: "Informar código CEST conforme nova classificação tributária.",
      }),
      makeEvidence({ id: evId, type: "xml", label: "CEST — ausente", xpath: inferXpath("CEST", docType), snippet: "<!-- Tag CEST não encontrada no XML -->" }),
    );
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
