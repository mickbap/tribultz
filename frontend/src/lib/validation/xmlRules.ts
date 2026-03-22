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
    const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, "i");
    const match = re.exec(xml);
    if (match) {
      return {
        tag,
        value: String(match[1] ?? "").trim(),
        snippet: match[0],
        index: match.index,
      };
    }
  }
  return null;
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

export function validateXmlWithRules(input: ValidationInput): ValidationResultV11 {
  const xml = input.xml.trim();
  const fingerprint = fnv1a32(`${input.documentType}|${xml}`);
  const jobId = `job_xml_${fingerprint}`;
  const auditId = `audit_xml_${fingerprint}`;

  const findings: Finding[] = [];
  const evidences: ValidationEvidence[] = [];
  const evidenceById = new Set<string>();

  const cst = firstTag(xml, ["CST"]);
  const cClassTrib = firstTag(xml, ["cClassTrib"]);
  const serviceCode = firstTag(xml, ["CodigoServico", "cServ", "codigoServico"]);
  const ncm = firstTag(xml, ["NCM"]);
  const cest = firstTag(xml, ["CEST"]);
  const valorCbs = firstTag(xml, ["ValorCBS"]);
  const valorIbs = firstTag(xml, ["ValorIBS"]);
  const aliquotaCbs = firstTag(xml, ["AliquotaCBS"]);
  const aliquotaIbs = firstTag(xml, ["AliquotaIBS"]);
  const baseCalculo = firstTag(xml, ["BaseCalculo"]);

  // ── Rules 1-3: field format checks (existing) ──────────────────────────────

  const fields = [
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
    },
  ] as const;

  for (const row of fields) {
    const evId = makeEvidenceId(row.findingId.replace(/^F_/, ""));
    const xpath = row.source ? inferXpath(row.source.tag, input.documentType) : inferXpath(row.field, input.documentType);
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
        makeEvidence({
          id: evId,
          type: "xml",
          label: `Trecho XML — ${row.field}`,
          xpath,
          snippet,
        }),
      );
      evidenceById.add(evId);
    }
  }

  // ── Rule 6: IBSCBS_MISSING — IBS/CBS fields must be present ────────────────

  const hasIbsCbs = !!(valorCbs && valorIbs && aliquotaCbs && aliquotaIbs);
  const ibscbsEvId = makeEvidenceId("IBSCBS_MISSING");
  if (!hasIbsCbs) {
    findings.push(
      makeFinding({
        id: "F_IBSCBS_MISSING",
        severity: "FATAL",
        ruleId: "IBSCBS_MISSING",
        title: "IBS/CBS ausentes na nota — obrigatório informar percentual e valor",
        field: "IBS/CBS",
        xpath: inferXpath("Valores", input.documentType),
        snippet: "<!-- Tags ValorCBS, ValorIBS, AliquotaCBS, AliquotaIBS não encontradas -->",
        evidenceId: ibscbsEvId,
        recommendation: "Informar alíquota e valor de IBS (0,90%) e CBS (0,10%) conforme LC 214.",
      }),
    );
    evidences.push(
      makeEvidence({
        id: ibscbsEvId,
        type: "xml",
        label: "IBS/CBS — campos ausentes",
        xpath: inferXpath("Valores", input.documentType),
        snippet: "<!-- Tags ValorCBS, ValorIBS, AliquotaCBS, AliquotaIBS não encontradas -->",
      }),
    );
    evidenceById.add(ibscbsEvId);
  }

  // ── Rule 7: IBSCBS_CALC — IBS/CBS calculation must match base × rate ───────

  if (hasIbsCbs && baseCalculo) {
    const base = parseFloat(baseCalculo.value);
    const cbsVal = parseFloat(valorCbs!.value);
    const ibsVal = parseFloat(valorIbs!.value);
    const cbsRate = parseFloat(aliquotaCbs!.value);
    const ibsRate = parseFloat(aliquotaIbs!.value);

    if (!isNaN(base) && !isNaN(cbsVal) && !isNaN(cbsRate)) {
      const expectedCbs = base * cbsRate;
      if (Math.abs(cbsVal - expectedCbs) > 0.01) {
        const cbsCalcEvId = makeEvidenceId("IBSCBS_CALC_CBS");
        findings.push(
          makeFinding({
            id: "F_IBSCBS_CALC_CBS",
            severity: "FATAL",
            ruleId: "IBSCBS_CALC",
            title: `Cálculo CBS incorreto — informado R$ ${cbsVal.toFixed(2)}, esperado R$ ${expectedCbs.toFixed(2)}`,
            field: "ValorCBS",
            xpath: inferXpath("ValorCBS", input.documentType),
            snippet: valorCbs!.snippet,
            evidenceId: cbsCalcEvId,
            recommendation: `CBS deve ser Base (${base.toFixed(2)}) × Alíquota (${cbsRate}) = R$ ${expectedCbs.toFixed(2)}. Corrigir valor.`,
          }),
        );
        evidences.push(
          makeEvidence({
            id: cbsCalcEvId,
            type: "xml",
            label: "CBS — cálculo divergente",
            xpath: inferXpath("ValorCBS", input.documentType),
            snippet: valorCbs!.snippet,
          }),
        );
        evidenceById.add(cbsCalcEvId);
      }
    }

    if (!isNaN(base) && !isNaN(ibsVal) && !isNaN(ibsRate)) {
      const expectedIbs = base * ibsRate;
      if (Math.abs(ibsVal - expectedIbs) > 0.01) {
        const ibsCalcEvId = makeEvidenceId("IBSCBS_CALC_IBS");
        findings.push(
          makeFinding({
            id: "F_IBSCBS_CALC_IBS",
            severity: "FATAL",
            ruleId: "IBSCBS_CALC",
            title: `Cálculo IBS incorreto — informado R$ ${ibsVal.toFixed(2)}, esperado R$ ${expectedIbs.toFixed(2)}`,
            field: "ValorIBS",
            xpath: inferXpath("ValorIBS", input.documentType),
            snippet: valorIbs!.snippet,
            evidenceId: ibsCalcEvId,
            recommendation: `IBS deve ser Base (${base.toFixed(2)}) × Alíquota (${ibsRate}) = R$ ${expectedIbs.toFixed(2)}. Corrigir valor.`,
          }),
        );
        evidences.push(
          makeEvidence({
            id: ibsCalcEvId,
            type: "xml",
            label: "IBS — cálculo divergente",
            xpath: inferXpath("ValorIBS", input.documentType),
            snippet: valorIbs!.snippet,
          }),
        );
        evidenceById.add(ibsCalcEvId);
      }
    }
  }

  // ── Rule 8: CEST_MISSING — CEST must be present ───────────────────────────

  if (!cest) {
    const cestMissingEvId = makeEvidenceId("CEST_MISSING");
    findings.push(
      makeFinding({
        id: "F_CEST_MISSING",
        severity: "FATAL",
        ruleId: "CEST_MISSING",
        title: "CEST ausente — código obrigatório conforme nova classificação",
        field: "CEST",
        xpath: inferXpath("CEST", input.documentType),
        snippet: "<!-- Tag CEST não encontrada no XML -->",
        evidenceId: cestMissingEvId,
        recommendation: "Informar código CEST conforme nova classificação tributária.",
      }),
    );
    evidences.push(
      makeEvidence({
        id: cestMissingEvId,
        type: "xml",
        label: "CEST — ausente",
        xpath: inferXpath("CEST", input.documentType),
        snippet: "<!-- Tag CEST não encontrada no XML -->",
      }),
    );
    evidenceById.add(cestMissingEvId);
  }

  // ── Rule 9: CEST_FORMAT — CEST must be exactly 7 digits ───────────────────

  if (cest && !/^\d{7}$/.test(cest.value)) {
    const cestFmtEvId = makeEvidenceId("CEST_FORMAT");
    findings.push(
      makeFinding({
        id: "F_CEST_FORMAT",
        severity: "FATAL",
        ruleId: "CEST_FORMAT",
        title: `CEST inválido (esperado 7 dígitos, encontrado "${cest.value}")`,
        field: "CEST",
        xpath: inferXpath(cest.tag, input.documentType),
        snippet: cest.snippet,
        evidenceId: cestFmtEvId,
        recommendation: "CEST deve ter exatamente 7 dígitos no formato novo. Verificar código atualizado.",
      }),
    );
    evidences.push(
      makeEvidence({
        id: cestFmtEvId,
        type: "xml",
        label: "CEST — formato inválido",
        xpath: inferXpath(cest.tag, input.documentType),
        snippet: cest.snippet,
      }),
    );
    evidenceById.add(cestFmtEvId);
  }

  // ── Rule 10: LAYOUT_PORTAL — required Portal Nacional structure ────────────

  const requiredLayoutTags = ["Valores", "PrestadorServico", "TomadorServico"] as const;
  const missingLayout = requiredLayoutTags.filter((tag) => !firstTag(xml, [tag]));
  if (missingLayout.length > 0) {
    const layoutEvId = makeEvidenceId("LAYOUT_PORTAL");
    findings.push(
      makeFinding({
        id: "F_LAYOUT_PORTAL",
        severity: "FATAL",
        ruleId: "LAYOUT_PORTAL",
        title: `Layout fora do padrão Portal Nacional — faltam: ${missingLayout.join(", ")}`,
        field: "Estrutura XML",
        xpath: inferXpath("infNfse", input.documentType),
        snippet: `<!-- Tags obrigatórias ausentes: ${missingLayout.join(", ")} -->`,
        evidenceId: layoutEvId,
        recommendation: "Documento deve seguir layout do Portal Nacional de NFS-e com todas as seções obrigatórias.",
      }),
    );
    evidences.push(
      makeEvidence({
        id: layoutEvId,
        type: "xml",
        label: "Layout — tags obrigatórias ausentes",
        xpath: inferXpath("infNfse", input.documentType),
        snippet: `<!-- Tags obrigatórias ausentes: ${missingLayout.join(", ")} -->`,
      }),
    );
    evidenceById.add(layoutEvId);
  }

  // ── NCM advisory (ALERT) ──────────────────────────────────────────────────

  const ncmEvId = makeEvidenceId("NCM_INFO");
  evidences.push(
    makeEvidence({
      id: ncmEvId,
      type: "xml",
      label: "NCM (avaliação informativa)",
      xpath: ncm ? inferXpath(ncm.tag, input.documentType) : inferXpath("NCM", input.documentType),
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
      xpath: ncm ? inferXpath(ncm.tag, input.documentType) : inferXpath("NCM", input.documentType),
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
          document_type: input.documentType,
          findings_total: findings.length,
          fatals: findings.filter((f) => f.severity === "FATAL").length,
        },
      },
    ],
  };

  return {
    job,
    audit,
    findings,
    evidences,
  };
}
