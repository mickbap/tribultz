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
      title: "cClassTrib inválido (esperado 6 dígitos)",
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
