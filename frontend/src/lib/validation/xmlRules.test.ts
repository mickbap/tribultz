import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { validateXmlWithRules, detectDocumentType, CST_TABLE } from "./xmlRules";

function fixture(name: string): string {
  return readFileSync(join(process.cwd(), "src/lib/validation/fixtures", name), "utf-8");
}

// ── Existing rules (S6) ─────────────────────────────────────────────────────

test("NFSe com erros gera findings FATAL esperados", () => {
  const result = validateXmlWithRules({
    tenantId: "tenant-a",
    documentType: "NFSE",
    xml: fixture("nfse-com-erros.xml"),
  });

  const fatalIds = result.findings.filter((f) => f.severity === "FATAL").map((f) => f.rule_id);
  // Regulamento 30/abr/2026: CEST_MISSING downgraded to ALERT (apenas ST) — issue #275
  // Original 3 format rules + IBSCBS_MISSING + LAYOUT_PORTAL
  assert.ok(fatalIds.includes("CST_3_DIGITS"), "expected CST_3_DIGITS");
  assert.ok(fatalIds.includes("CCLASSTRIB_6_DIGITS"), "expected CCLASSTRIB_6_DIGITS");
  assert.ok(fatalIds.includes("SERVICE_CODE_6_DIGITS"), "expected SERVICE_CODE_6_DIGITS");
  assert.ok(fatalIds.includes("IBSCBS_MISSING"), "expected IBSCBS_MISSING");
  assert.ok(fatalIds.includes("LAYOUT_PORTAL"), "expected LAYOUT_PORTAL");
  assert.equal(fatalIds.length, 5);
});

test("NFSe ok não gera FATAL", () => {
  const result = validateXmlWithRules({
    tenantId: "tenant-a",
    documentType: "NFSE",
    xml: fixture("nfse-ok.xml"),
  });
  assert.equal(result.findings.some((f) => f.severity === "FATAL"), false);
  assert.equal(result.findings.some((f) => f.severity === "ALERT"), true);
});

test("NF-e smoke retorna estrutura mínima de job/audit/evidências", () => {
  const result = validateXmlWithRules({
    tenantId: "tenant-b",
    documentType: "NFE",
    xml: fixture("nfe-smoke.xml"),
  });
  assert.ok(result.job.id.startsWith("job_xml_"));
  assert.ok(result.audit.id.startsWith("audit_xml_"));
  assert.ok(result.evidences.length > 0);
});

test("determinismo: mesmo XML + tipo gera mesmos finding ids e ordem", () => {
  const xml = fixture("nfse-com-erros.xml");
  const a = validateXmlWithRules({
    tenantId: "tenant-a",
    documentType: "NFSE",
    xml,
  });
  const b = validateXmlWithRules({
    tenantId: "tenant-a",
    documentType: "NFSE",
    xml,
  });
  assert.deepEqual(
    a.findings.map((f) => ({ id: f.id, severity: f.severity, rule: f.rule_id })),
    b.findings.map((f) => ({ id: f.id, severity: f.severity, rule: f.rule_id })),
  );
  assert.deepEqual(
    a.evidences.map((e) => ({ id: e.id, type: e.type, xpath: e.xpath })),
    b.evidences.map((e) => ({ id: e.id, type: e.type, xpath: e.xpath })),
  );
});

// ── New rules (S7) — IBSCBS_MISSING ─────────────────────────────────────────

test("IBSCBS_MISSING: nota sem tags IBS/CBS gera FATAL", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<NFS-e><infNfse>
  <PrestadorServico><RazaoSocial>X</RazaoSocial></PrestadorServico>
  <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
  <PrestacaoServico>
    <Servico>
      <CodigoServico>123456</CodigoServico>
      <cClassTrib>654321</cClassTrib>
      <CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST>
    </Servico>
    <Valores><BaseCalculo>10000.00</BaseCalculo></Valores>
  </PrestacaoServico>
</infNfse></NFS-e>`;
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFSE", xml });
  const f = result.findings.find((f) => f.rule_id === "IBSCBS_MISSING");
  assert.ok(f, "IBSCBS_MISSING finding expected");
  assert.equal(f!.severity, "FATAL");
});

// ── New rules (S7) — IBSCBS_CALC ────────────────────────────────────────────

test("IBSCBS_CALC: CBS incorreto gera FATAL com valor esperado", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<NFS-e><infNfse>
  <PrestadorServico><RazaoSocial>X</RazaoSocial></PrestadorServico>
  <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
  <PrestacaoServico>
    <Servico>
      <CodigoServico>123456</CodigoServico>
      <cClassTrib>654321</cClassTrib>
      <CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST>
    </Servico>
    <Valores>
      <BaseCalculo>10000.00</BaseCalculo>
      <AliquotaCBS>0.0010</AliquotaCBS><ValorCBS>15.00</ValorCBS>
      <AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>90.00</ValorIBS>
    </Valores>
  </PrestacaoServico>
</infNfse></NFS-e>`;
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFSE", xml });
  const cbsF = result.findings.find((f) => f.id === "F_IBSCBS_CALC_CBS");
  assert.ok(cbsF, "CBS calc finding expected");
  assert.equal(cbsF!.severity, "FATAL");
  assert.ok(cbsF!.title.includes("15.00"), "title should mention informed value");
  assert.ok(cbsF!.title.includes("10.00"), "title should mention expected value");
  // IBS should pass (90.00 = 10000 * 0.0090)
  const ibsF = result.findings.find((f) => f.id === "F_IBSCBS_CALC_IBS");
  assert.equal(ibsF, undefined, "IBS calc should pass");
});

test("IBSCBS_CALC: IBS incorreto gera FATAL", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<NFS-e><infNfse>
  <PrestadorServico><RazaoSocial>X</RazaoSocial></PrestadorServico>
  <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
  <PrestacaoServico>
    <Servico>
      <CodigoServico>123456</CodigoServico>
      <cClassTrib>654321</cClassTrib>
      <CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST>
    </Servico>
    <Valores>
      <BaseCalculo>10000.00</BaseCalculo>
      <AliquotaCBS>0.0010</AliquotaCBS><ValorCBS>10.00</ValorCBS>
      <AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>50.00</ValorIBS>
    </Valores>
  </PrestacaoServico>
</infNfse></NFS-e>`;
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFSE", xml });
  const ibsF = result.findings.find((f) => f.id === "F_IBSCBS_CALC_IBS");
  assert.ok(ibsF, "IBS calc finding expected");
  assert.equal(ibsF!.severity, "FATAL");
});

test("IBSCBS_CALC: valores corretos não geram finding de cálculo", () => {
  const result = validateXmlWithRules({
    tenantId: "t",
    documentType: "NFSE",
    xml: fixture("nfse-ok.xml"),
  });
  assert.equal(result.findings.find((f) => f.rule_id === "IBSCBS_CALC"), undefined);
});

// ── New rules (S7) — CEST_MISSING ───────────────────────────────────────────

test("CEST_MISSING: nota sem CEST gera ALERT (regulamento 30/abr/2026 — apenas ST)", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<NFS-e><infNfse>
  <PrestadorServico><RazaoSocial>X</RazaoSocial></PrestadorServico>
  <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
  <PrestacaoServico>
    <Servico>
      <CodigoServico>123456</CodigoServico>
      <cClassTrib>654321</cClassTrib>
      <CST>090</CST><NCM>84713012</NCM>
    </Servico>
    <Valores>
      <BaseCalculo>10000.00</BaseCalculo>
      <AliquotaCBS>0.0010</AliquotaCBS><ValorCBS>10.00</ValorCBS>
      <AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>90.00</ValorIBS>
    </Valores>
  </PrestacaoServico>
</infNfse></NFS-e>`;
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFSE", xml });
  const f = result.findings.find((f) => f.rule_id === "CEST_MISSING");
  assert.ok(f, "CEST_MISSING finding expected");
  assert.equal(f!.severity, "ALERT"); // downgraded per regulamento 30/abr/2026
});

// ── New rules (S7) — CEST_FORMAT ────────────────────────────────────────────

test("CEST_FORMAT: CEST com 5 dígitos gera FATAL", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<NFS-e><infNfse>
  <PrestadorServico><RazaoSocial>X</RazaoSocial></PrestadorServico>
  <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
  <PrestacaoServico>
    <Servico>
      <CodigoServico>123456</CodigoServico>
      <cClassTrib>654321</cClassTrib>
      <CST>090</CST><NCM>84713012</NCM>
      <CEST>21049</CEST>
    </Servico>
    <Valores>
      <BaseCalculo>10000.00</BaseCalculo>
      <AliquotaCBS>0.0010</AliquotaCBS><ValorCBS>10.00</ValorCBS>
      <AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>90.00</ValorIBS>
    </Valores>
  </PrestacaoServico>
</infNfse></NFS-e>`;
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFSE", xml });
  const f = result.findings.find((f) => f.rule_id === "CEST_FORMAT");
  assert.ok(f, "CEST_FORMAT finding expected");
  assert.equal(f!.severity, "FATAL");
  assert.ok(f!.title.includes("21049"), "title should show the invalid value");
});

test("CEST_FORMAT: CEST com 7 dígitos não gera finding", () => {
  const result = validateXmlWithRules({
    tenantId: "t",
    documentType: "NFSE",
    xml: fixture("nfse-ok.xml"),
  });
  assert.equal(result.findings.find((f) => f.rule_id === "CEST_FORMAT"), undefined);
});

// ── New rules (S7) — LAYOUT_PORTAL ──────────────────────────────────────────

test("LAYOUT_PORTAL: nota sem PrestadorServico/TomadorServico/Valores gera FATAL", () => {
  const result = validateXmlWithRules({
    tenantId: "t",
    documentType: "NFSE",
    xml: fixture("nfse-com-erros.xml"),
  });
  const f = result.findings.find((f) => f.rule_id === "LAYOUT_PORTAL");
  assert.ok(f, "LAYOUT_PORTAL finding expected");
  assert.equal(f!.severity, "FATAL");
  assert.ok(f!.title.includes("Valores"), "should mention missing Valores");
  assert.ok(f!.title.includes("PrestadorServico"), "should mention missing PrestadorServico");
  assert.ok(f!.title.includes("TomadorServico"), "should mention missing TomadorServico");
});

test("LAYOUT_PORTAL: nota completa não gera finding de layout", () => {
  const result = validateXmlWithRules({
    tenantId: "t",
    documentType: "NFSE",
    xml: fixture("nfse-ok.xml"),
  });
  assert.equal(result.findings.find((f) => f.rule_id === "LAYOUT_PORTAL"), undefined);
});

// ── S11: detectDocumentType ─────────────────────────────────────────────────

test("detectDocumentType: NFS-e detected from NFS-e XML", () => {
  assert.equal(detectDocumentType(fixture("nfse-ok.xml")), "NFSE");
});

test("detectDocumentType: NFE detected from nfeProc with mod=55", () => {
  assert.equal(detectDocumentType(fixture("nfe-ok.xml")), "NFE");
});

test("detectDocumentType: NFCE detected from nfeProc with mod=65", () => {
  assert.equal(detectDocumentType(fixture("nfce-ok.xml")), "NFCE");
});

// ── S11: CST_TABLE ──────────────────────────────────────────────────────────

test("CST_TABLE has 14 entries per NT 2025.002-RTC", () => {
  assert.equal(Object.keys(CST_TABLE).length, 14);
  assert.ok(CST_TABLE["000"], "CST 000 should exist");
  assert.ok(CST_TABLE["070"], "CST 070 should exist");
  assert.ok(CST_TABLE["620"], "CST 620 should exist");
  assert.ok(CST_TABLE["830"], "CST 830 should exist");
});

// ── S11: NF-e ok — no FATALs ───────────────────────────────────────────────

test("NF-e ok não gera FATAL", () => {
  const result = validateXmlWithRules({
    tenantId: "tenant-a",
    documentType: "NFE",
    xml: fixture("nfe-ok.xml"),
  });
  const fatals = result.findings.filter((f) => f.severity === "FATAL");
  assert.equal(fatals.length, 0, `Unexpected FATALs: ${fatals.map((f) => f.rule_id).join(", ")}`);
  assert.ok(result.findings.some((f) => f.severity === "ALERT"), "Should have ALERT findings");
});

// ── S11: NFC-e ok — no FATALs ──────────────────────────────────────────────

test("NFC-e ok não gera FATAL", () => {
  const result = validateXmlWithRules({
    tenantId: "tenant-a",
    documentType: "NFCE",
    xml: fixture("nfce-ok.xml"),
  });
  const fatals = result.findings.filter((f) => f.severity === "FATAL");
  assert.equal(fatals.length, 0, `Unexpected FATALs: ${fatals.map((f) => f.rule_id).join(", ")}`);
});

// ── S11: IBSCBS_SPLIT — vIBS != vIBSUF + vIBSMun ──────────────────────────

test("IBSCBS_SPLIT: NF-e com split incorreto gera FATAL", () => {
  const result = validateXmlWithRules({
    tenantId: "t",
    documentType: "NFE",
    xml: fixture("nfe-ibs-split-error.xml"),
  });
  const f = result.findings.find((f) => f.rule_id === "IBSCBS_SPLIT");
  assert.ok(f, "IBSCBS_SPLIT finding expected");
  assert.equal(f!.severity, "FATAL");
  assert.ok(f!.title.includes("1.50"), "should show declared vIBS");
});

// ── S11: IBSCBS_UF_CALC / IBSCBS_MUN_CALC ──────────────────────────────────

test("IBSCBS_UF_CALC: NF-e ok não gera finding de cálculo UF", () => {
  const result = validateXmlWithRules({
    tenantId: "t",
    documentType: "NFE",
    xml: fixture("nfe-ok.xml"),
  });
  assert.equal(result.findings.find((f) => f.rule_id === "IBSCBS_UF_CALC"), undefined);
  assert.equal(result.findings.find((f) => f.rule_id === "IBSCBS_MUN_CALC"), undefined);
});

// ── S11: CST_VALID — unknown CST ───────────────────────────────────────────

test("CST_VALID: NF-e com CST 999 gera FATAL (código desconhecido)", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod></ide>
  <emit><CNPJ>12345678000195</CNPJ></emit>
  <det nItem="1">
    <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>
    <imposto>
      <IBSCBS>
        <CST>999</CST>
        <cClassTrib>654321</cClassTrib>
        <gIBSCBS>
          <vBC>1000.00</vBC>
          <gIBSUF><pIBSUF>0.0005</pIBSUF><vIBSUF>0.50</vIBSUF></gIBSUF>
          <gIBSMun><pIBSMun>0.0005</pIBSMun><vIBSMun>0.50</vIBSMun></gIBSMun>
          <vIBS>1.00</vIBS>
          <gCBS><pCBS>0.0090</pCBS><vCBS>9.00</vCBS></gCBS>
        </gIBSCBS>
      </IBSCBS>
    </imposto>
  </det>
  <total><IBSCBSTot><vIBS>1.00</vIBS><vCBS>9.00</vCBS></IBSCBSTot></total>
</infNFe></NFe></nfeProc>`;
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "CST_VALID");
  assert.ok(f, "CST_VALID finding expected");
  assert.equal(f!.severity, "FATAL");
});

// ── S11: CST_GROUP_MATCH — CST 000 without gIBSCBS ─────────────────────────

test("CST_GROUP_MATCH: NF-e with CST 000 but no gIBSCBS gera FATAL", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod></ide>
  <emit><CNPJ>12345678000195</CNPJ></emit>
  <det nItem="1">
    <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>
    <imposto>
      <IBSCBS>
        <CST>000</CST>
        <cClassTrib>654321</cClassTrib>
      </IBSCBS>
    </imposto>
  </det>
  <total><IBSCBSTot><vIBS>0</vIBS><vCBS>0</vCBS></IBSCBSTot></total>
</infNFe></NFe></nfeProc>`;
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "CST_GROUP_MATCH");
  assert.ok(f, "CST_GROUP_MATCH finding expected — CST 000 requires gIBSCBS");
});

// ── S11: LAYOUT_NFE — NF-e structure check ──────────────────────────────────

test("LAYOUT_NFE: NF-e sem emit gera FATAL", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod></ide>
  <det nItem="1">
    <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>100</vProd></prod>
    <imposto><IBSCBS><CST>070</CST><cClassTrib>654321</cClassTrib></IBSCBS></imposto>
  </det>
</infNFe></NFe></nfeProc>`;
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "LAYOUT_NFE");
  assert.ok(f, "LAYOUT_NFE finding expected");
  assert.ok(f!.title.includes("emit") || f!.title.includes("total"), "should mention missing tag");
});

// ── S11: NF-e does NOT trigger LAYOUT_PORTAL (NFS-e only) ──────────────────

test("NF-e não aciona regra LAYOUT_PORTAL", () => {
  const result = validateXmlWithRules({
    tenantId: "t",
    documentType: "NFE",
    xml: fixture("nfe-ok.xml"),
  });
  assert.equal(result.findings.find((f) => f.rule_id === "LAYOUT_PORTAL"), undefined);
});

// ── S11: NF-e does NOT trigger SERVICE_CODE_6_DIGITS ────────────────────────

test("NF-e não valida CodigoServico (usa CFOP)", () => {
  const result = validateXmlWithRules({
    tenantId: "t",
    documentType: "NFE",
    xml: fixture("nfe-ok.xml"),
  });
  assert.equal(result.findings.find((f) => f.rule_id === "SERVICE_CODE_6_DIGITS"), undefined);
});
