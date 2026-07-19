import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { validateXmlWithRules, detectDocumentType, CST_TABLE, NT_VERSION } from "./xmlRules";

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

test("CEST_MISSING: NCM não-ST sem CEST gera ALERT (Conv. 142/2018, #275)", () => {
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
  assert.equal(f!.severity, "ALERT"); // NCM 84713012 fora do subset ST
});

test("CEST_MISSING: NCM ST sem CEST gera FATAL com segmento (#275 fase 2)", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<NFS-e><infNfse>
  <PrestadorServico><RazaoSocial>X</RazaoSocial></PrestadorServico>
  <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
  <PrestacaoServico>
    <Servico>
      <CodigoServico>123456</CodigoServico>
      <cClassTrib>654321</cClassTrib>
      <CST>090</CST><NCM>22021000</NCM>
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
  assert.equal(f!.severity, "FATAL"); // NCM 22021000 (refrigerante) é ST
  assert.match(f!.title, /bebidas_nao_alcoolicas/);
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

// ── S22 (#310): NT 2025.002-RTC v1.40 — versão alvo + tolerância de leiaute ──

test("NT_VERSION declara v1.40", () => {
  assert.equal(NT_VERSION, "1.40");
});

test("NF-e v1.40 (campos/grupos novos) não gera FATAL", () => {
  const result = validateXmlWithRules({
    tenantId: "tenant-a",
    documentType: "NFE",
    xml: fixture("nfe-v140-ok.xml"),
  });
  const fatals = result.findings.filter((f) => f.severity === "FATAL");
  assert.equal(
    fatals.length,
    0,
    `v1.40 não deve gerar FATAL — campos novos (cIndOp, ISUFEmit, gALCZFMCBS, refDFeAnt, gDevTrib) devem ser tolerados. FATALs: ${fatals.map((f) => f.rule_id).join(", ")}`,
  );
});

// ── S22 (#311): IBS/CBS obrigatório ciente do CRT (NT v1.40) ─────────────────
// CRT 3 (Regime Normal): obrigatório 03/08/2026 → FATAL.
// CRT 1/2/4 (Simples/MEI): obrigatório só 04/01/2027 → WARNING (não falso-rejeitar).

const nfeSemIbscbs = (crt: string) => `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod></ide>
  <emit><CNPJ>12345678000195</CNPJ><CRT>${crt}</CRT></emit>
  <det nItem="1">
    <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>
    <imposto><ICMS><ICMSSN101><CST>101</CST></ICMSSN101></ICMS></imposto>
  </det>
  <total></total>
</infNFe></NFe></nfeProc>`;

test("IBSCBS_MISSING: CRT 1 (Simples) sem IBS/CBS → WARNING (#311)", () => {
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml: nfeSemIbscbs("1") });
  const f = result.findings.find((f) => f.rule_id === "IBSCBS_MISSING");
  assert.ok(f, "IBSCBS_MISSING esperado");
  assert.equal(f!.severity, "WARNING");
});

test("IBSCBS_MISSING: CRT 4 (MEI) sem IBS/CBS → WARNING (#311)", () => {
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml: nfeSemIbscbs("4") });
  const f = result.findings.find((f) => f.rule_id === "IBSCBS_MISSING");
  assert.equal(f?.severity, "WARNING");
});

test("IBSCBS_MISSING: CRT 3 (Regime Normal) sem IBS/CBS → FATAL (#311)", () => {
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml: nfeSemIbscbs("3") });
  const f = result.findings.find((f) => f.rule_id === "IBSCBS_MISSING");
  assert.ok(f, "IBSCBS_MISSING esperado");
  assert.equal(f!.severity, "FATAL");
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

// ── S22 (#277): MONOFASICO_ZERO — CST 620 downstream deve ter vCBS=vIBS=0 ────

test("MONOFASICO_ZERO: NF-e com CST 620 e vCBS>0 gera FATAL", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod></ide>
  <emit><CNPJ>12345678000195</CNPJ></emit>
  <det nItem="1">
    <prod><NCM>27101259</NCM><vProd>100</vProd></prod>
    <imposto><IBSCBS>
      <CST>620</CST>
      <cClassTrib>620001</cClassTrib>
      <gIBSCBSMono>
        <vBC>1000.00</vBC>
        <vIBS>1.00</vIBS>
        <vCBS>9.00</vCBS>
      </gIBSCBSMono>
    </IBSCBS></imposto>
  </det>
  <total><IBSCBSTot><vIBS>1.00</vIBS><vCBS>9.00</vCBS></IBSCBSTot></total>
</infNFe></NFe></nfeProc>`;
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "MONOFASICO_ZERO");
  assert.ok(f, "MONOFASICO_ZERO finding expected — CST 620 downstream com valor > 0");
  assert.equal(f!.severity, "FATAL");
});

test("MONOFASICO_ZERO: NF-e com CST 620 e vCBS=vIBS=0 não gera finding", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod></ide>
  <emit><CNPJ>12345678000195</CNPJ></emit>
  <det nItem="1">
    <prod><NCM>27101259</NCM><vProd>100</vProd></prod>
    <imposto><IBSCBS>
      <CST>620</CST>
      <cClassTrib>620001</cClassTrib>
      <gIBSCBSMono>
        <vBC>1000.00</vBC>
        <vIBS>0.00</vIBS>
        <vCBS>0.00</vCBS>
      </gIBSCBSMono>
    </IBSCBS></imposto>
  </det>
  <total><IBSCBSTot><vIBS>0.00</vIBS><vCBS>0.00</vCBS></IBSCBSTot></total>
</infNFe></NFe></nfeProc>`;
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  assert.equal(result.findings.find((f) => f.rule_id === "MONOFASICO_ZERO"), undefined);
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

// ── NT 2025.002 V1.36 — dPrevEntrega rules (issue #286) ─────────────────────

// NF-e helper: minimal valid NF-e skeleton
function nfeWithFields(extra: string): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe><ide>
  <dhEmi>2026-05-27T10:00:00-03:00</dhEmi>
  <dhSaiEnt>2026-05-27T10:00:00-03:00</dhSaiEnt>
  ${extra}
</ide><emit><CNPJ>12345678000195</CNPJ></emit>
<det nItem="1"><prod><NCM>84713012</NCM><CEST>2104900</CEST></prod>
  <imposto><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib>
    <gIBSCBS><vBC>1000</vBC><gIBSUF><pIBSUF>0.9</pIBSUF><vIBSUF>9</vIBSUF></gIBSUF>
    <gIBSMun><pIBSMun>0.1</pIBSMun><vIBSMun>1</vIBSMun></gIBSMun><vIBS>10</vIBS>
    <gCBS><pCBS>0.1</pCBS><vCBS>1</vCBS></gCBS></gIBSCBS>
  </IBSCBS></imposto></det>
<total><emit/></total>
</infNFe></NFe></nfeProc>`;
}

test("DPREV_ENTREGA_FRETE: dPrevEntrega + modFrete FOB(1) gera FATAL", () => {
  const xml = nfeWithFields(`
    <dPrevEntrega>2026-06-05</dPrevEntrega>
    <transp><modFrete>1</modFrete></transp>
  `).replace("</ide>", "</ide>");
  // inject modFrete inside the XML
  const xml2 = xml.replace("</nfeProc>", `<transp><modFrete>1</modFrete></transp></nfeProc>`)
    .replace("<dhEmi>", "<dPrevEntrega>2026-06-05</dPrevEntrega><dhEmi>");
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml: xml2 });
  const f = result.findings.find((f) => f.rule_id === "DPREV_ENTREGA_FRETE");
  assert.ok(f, "DPREV_ENTREGA_FRETE finding expected when FOB with dPrevEntrega");
  assert.equal(f!.severity, "FATAL");
});

test("DPREV_ENTREGA_COMPETENCIA: entrega em junho, emissão em maio gera ALERT", () => {
  const xml = nfeWithFields(`<dPrevEntrega>2026-06-15</dPrevEntrega>`);
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "DPREV_ENTREGA_COMPETENCIA");
  assert.ok(f, "DPREV_ENTREGA_COMPETENCIA expected when delivery in different month");
  assert.equal(f!.severity, "ALERT");
  assert.ok(f!.title.includes("2026-06"), "title should mention delivery month");
  assert.ok(f!.title.includes("2026-05"), "title should mention emission month");
});

test("DPREV_ENTREGA_COMPETENCIA: mesmo mês não gera finding", () => {
  const xml = nfeWithFields(`<dPrevEntrega>2026-05-31</dPrevEntrega>`);
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  assert.equal(result.findings.find((f) => f.rule_id === "DPREV_ENTREGA_COMPETENCIA"), undefined);
});

test("DPREV_ENTREGA_CIF_AUSENTE: modFrete=0 sem dPrevEntrega gera ALERT", () => {
  const xml = nfeWithFields("").replace("</nfeProc>",
    "<transp><modFrete>0</modFrete></transp></nfeProc>");
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "DPREV_ENTREGA_CIF_AUSENTE");
  assert.ok(f, "DPREV_ENTREGA_CIF_AUSENTE expected for CIF without dPrevEntrega");
  assert.equal(f!.severity, "ALERT");
});

test("DPREV_ENTREGA_CIF_AUSENTE: NFS-e não aciona regra", () => {
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFSE",
    xml: fixture("nfse-ok.xml") });
  assert.equal(result.findings.find((f) => f.rule_id === "DPREV_ENTREGA_CIF_AUSENTE"), undefined);
});

// ── SPLIT_PAYMENT_INDPAG (#276) ─────────────────────────────────────────────

function nfeWithIndPag(opts: { indPag: string; vCBS: string; vIBS: string; cst?: string }): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <emit><CNPJ>11111111000111</CNPJ></emit>
  <det><prod><NCM>22021000</NCM></prod>
    <IBSCBS>
      <CST>${opts.cst ?? "000"}</CST><cClassTrib>100100</cClassTrib>
      <vBC>1000.00</vBC>
      <pCBS>0.0010</pCBS><vCBS>${opts.vCBS}</vCBS>
      <pIBSUF>0.0040</pIBSUF><vIBSUF>${(parseFloat(opts.vIBS) / 2).toFixed(2)}</vIBSUF>
      <pIBSMun>0.0050</pIBSMun><vIBSMun>${(parseFloat(opts.vIBS) / 2).toFixed(2)}</vIBSMun>
      <vIBS>${opts.vIBS}</vIBS>
    </IBSCBS>
  </det>
  <total><IBSCBSTot><vCBS>${opts.vCBS}</vCBS><vIBS>${opts.vIBS}</vIBS></IBSCBSTot></total>
  <cobr><dup><indPag>${opts.indPag}</indPag></dup></cobr>
</infNFe></NFe></nfeProc>`;
}

test("SPLIT_PAYMENT_INDPAG: indPag=3 (Pix) sem CBS/IBS gera FATAL", () => {
  const xml = nfeWithIndPag({ indPag: "3", vCBS: "0.00", vIBS: "0.00" });
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "SPLIT_PAYMENT_INDPAG");
  assert.ok(f, "SPLIT_PAYMENT_INDPAG expected");
  assert.equal(f!.severity, "FATAL");
  assert.match(f!.title, /Pix\/TED/);
});

test("SPLIT_PAYMENT_INDPAG: indPag=4 (cartão) sem CBS/IBS gera FATAL", () => {
  const xml = nfeWithIndPag({ indPag: "4", vCBS: "0.00", vIBS: "0.00" });
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "SPLIT_PAYMENT_INDPAG");
  assert.ok(f, "SPLIT_PAYMENT_INDPAG expected");
  assert.equal(f!.severity, "FATAL");
  assert.match(f!.title, /cartão/);
});

test("SPLIT_PAYMENT_INDPAG: indPag=3 com CBS/IBS lançados não gera finding", () => {
  const xml = nfeWithIndPag({ indPag: "3", vCBS: "1.00", vIBS: "9.00" });
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  assert.equal(result.findings.find((f) => f.rule_id === "SPLIT_PAYMENT_INDPAG"), undefined);
});

test("SPLIT_PAYMENT_INDPAG: indPag=3 com CST 070 (imunidade) não gera finding", () => {
  const xml = nfeWithIndPag({ indPag: "3", vCBS: "0.00", vIBS: "0.00", cst: "070" });
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  assert.equal(result.findings.find((f) => f.rule_id === "SPLIT_PAYMENT_INDPAG"), undefined);
});

test("SPLIT_PAYMENT_INDPAG: indPag=0 (à vista) sem CBS/IBS não gera finding", () => {
  const xml = nfeWithIndPag({ indPag: "0", vCBS: "0.00", vIBS: "0.00" });
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  assert.equal(result.findings.find((f) => f.rule_id === "SPLIT_PAYMENT_INDPAG"), undefined);
});

// ── Item 1: janela sem penalidades — Ato Conjunto RFB/CGIBS nº 1/2025 art. 3º ──
// Multas por obrigação acessória de IBS/CBS suspensas para fatos geradores até
// 31/07/2026 (regulamentos publicados 30/04/2026). A partir de 01/08/2026 a
// penalidade volta a ser aplicável → severidade FATAL. pedagogicalMode (LC 227)
// permanece como override manual independente da data.

const nfeAcessoriaErr = (crt: string, dhEmi?: string) => `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod>${dhEmi ? `<dhEmi>${dhEmi}</dhEmi>` : ""}</ide>
  <emit><CNPJ>12345678000195</CNPJ><CRT>${crt}</CRT></emit>
  <det nItem="1">
    <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>
    <imposto><ICMS><ICMSSN101><CST>101</CST></ICMSSN101></ICMS></imposto>
  </det>
  <total></total>
</infNFe></NFe></nfeProc>`;

test("janela: CRT 3 com dhEmi 2026-07-31 → IBSCBS_MISSING WARNING (sem penalidade)", () => {
  const result = validateXmlWithRules({
    tenantId: "t", documentType: "NFE", xml: nfeAcessoriaErr("3", "2026-07-31T10:00:00-03:00"),
  });
  const f = result.findings.find((f) => f.rule_id === "IBSCBS_MISSING");
  assert.ok(f, "IBSCBS_MISSING esperado");
  assert.equal(f!.severity, "WARNING");
  assert.match(f!.recommendation ?? "", /Ato Conjunto RFB\/CGIBS/);
});

test("janela: CRT 3 com dhEmi 2026-08-01 → IBSCBS_MISSING FATAL (janela fechada)", () => {
  const result = validateXmlWithRules({
    tenantId: "t", documentType: "NFE", xml: nfeAcessoriaErr("3", "2026-08-01T10:00:00-03:00"),
  });
  const f = result.findings.find((f) => f.rule_id === "IBSCBS_MISSING");
  assert.equal(f?.severity, "FATAL");
});

test("janela: CRT 3 com dhEmi 2026-08-15 → IBSCBS_MISSING FATAL", () => {
  const result = validateXmlWithRules({
    tenantId: "t", documentType: "NFE", xml: nfeAcessoriaErr("3", "2026-08-15T10:00:00-03:00"),
  });
  assert.equal(result.findings.find((f) => f.rule_id === "IBSCBS_MISSING")?.severity, "FATAL");
});

test("janela: CRT 3 sem dhEmi → IBSCBS_MISSING FATAL (comportamento preservado)", () => {
  const result = validateXmlWithRules({
    tenantId: "t", documentType: "NFE", xml: nfeAcessoriaErr("3"),
  });
  assert.equal(result.findings.find((f) => f.rule_id === "IBSCBS_MISSING")?.severity, "FATAL");
});

test("janela: fora da janela + pedagogicalMode → WARNING com nota LC 227", () => {
  const result = validateXmlWithRules({
    tenantId: "t", documentType: "NFE", xml: nfeAcessoriaErr("3", "2026-09-10T10:00:00-03:00"),
    pedagogicalMode: true,
  });
  const f = result.findings.find((f) => f.rule_id === "IBSCBS_MISSING");
  assert.equal(f?.severity, "WARNING");
  assert.match(f!.recommendation ?? "", /LC 227\/2026/);
});

test("janela: regra de formato (CST_3_DIGITS) dentro da janela → WARNING", () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod><dhEmi>2026-05-10T10:00:00-03:00</dhEmi></ide>
  <emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>
  <det nItem="1">
    <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>
    <imposto><IBSCBS><CST>00</CST><cClassTrib>000001</cClassTrib></IBSCBS></imposto>
  </det>
  <total></total>
</infNFe></NFe></nfeProc>`;
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  assert.equal(result.findings.find((f) => f.rule_id === "CST_3_DIGITS")?.severity, "WARNING");
});

test("janela: regra NÃO-acessória (IBSCBS_SPLIT) dentro da janela permanece FATAL", () => {
  // fixture nfe-ibs-split-error.xml tem dhEmi 2026-03-23 (dentro da janela)
  const result = validateXmlWithRules({
    tenantId: "t", documentType: "NFE", xml: fixture("nfe-ibs-split-error.xml"),
  });
  const f = result.findings.find((f) => f.rule_id === "IBSCBS_SPLIT");
  assert.equal(f?.severity, "FATAL", "regra de cálculo não é obrigação acessória — não entra na janela");
});

// ── Item 2: IMPORT_IBSCBS_REQUIRED — incidência na importação (Decreto 12.955/2026) ──
// Importação (CFOP 3xxx ou grupo DI/DUIMP) é tributável por IBS/CBS independente
// de importador habitual (art. 65). Escopo: grupo IBSCBS presente porém zerado com
// CST tributável. Export (7xxx) e internas (1/2/5/6xxx) ficam fora.

const nfeImport = (o: {
  cfop?: string; cst?: string; dhEmi?: string; vCBS?: string; vIBS?: string;
  di?: boolean; noIbscbs?: boolean;
} = {}) => {
  const cfop = o.cfop ?? "3102";
  const cst = o.cst ?? "000";
  const vCBS = o.vCBS ?? "0.00";
  const vIBS = o.vIBS ?? "0.00";
  const di = o.di ? "<DI><nDI>2603001234</nDI></DI>" : "";
  const ibscbs = o.noIbscbs ? "" : `<IBSCBS><CST>${cst}</CST><cClassTrib>000001</cClassTrib>
        <gIBSCBS><vBC>1000.00</vBC>
          <gIBSUF><pIBSUF>0</pIBSUF><vIBSUF>0.00</vIBSUF></gIBSUF>
          <gIBSMun><pIBSMun>0</pIBSMun><vIBSMun>0.00</vIBSMun></gIBSMun>
          <vIBS>${vIBS}</vIBS><gCBS><pCBS>0</pCBS><vCBS>${vCBS}</vCBS></gCBS>
        </gIBSCBS></IBSCBS>`;
  return `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod>${o.dhEmi ? `<dhEmi>${o.dhEmi}</dhEmi>` : ""}</ide>
  <emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>
  <det nItem="1">
    <prod><CFOP>${cfop}</CFOP><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd>${di}</prod>
    <imposto>${ibscbs}</imposto>
  </det>
  <total><IBSCBSTot><vIBS>${vIBS}</vIBS><vCBS>${vCBS}</vCBS></IBSCBSTot></total>
</infNFe></NFe></nfeProc>`;
};

const importFinding = (xml: string) =>
  validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml })
    .findings.find((f) => f.rule_id === "IMPORT_IBSCBS_REQUIRED");

test("IMPORT: CFOP 3xxx zerado + CST tributável (fora da janela) → FATAL", () => {
  const f = importFinding(nfeImport({ cfop: "3102", dhEmi: "2026-09-10T10:00:00-03:00" }));
  assert.ok(f, "IMPORT_IBSCBS_REQUIRED esperado");
  assert.equal(f!.severity, "FATAL");
  assert.match(f!.recommendation ?? "", /Decreto 12\.955\/2026/);
});

test("IMPORT: detecção via grupo DI mesmo com CFOP interno → FATAL", () => {
  const f = importFinding(nfeImport({ cfop: "1102", di: true, dhEmi: "2026-09-10T10:00:00-03:00" }));
  assert.ok(f, "IMPORT_IBSCBS_REQUIRED esperado (DI presente)");
  assert.equal(f!.severity, "FATAL");
});

test("IMPORT: importação tributada (vCBS/vIBS > 0) → sem finding", () => {
  assert.equal(importFinding(nfeImport({ cfop: "3102", vCBS: "9.00", vIBS: "1.00" })), undefined);
});

test("IMPORT: CST 070 (imunidade) zerado → sem finding", () => {
  assert.equal(importFinding(nfeImport({ cfop: "3102", cst: "070" })), undefined);
});

test("IMPORT: CST 200 (diferimento) zerado → sem finding (tributo postergado)", () => {
  assert.equal(importFinding(nfeImport({ cfop: "3102", cst: "200" })), undefined);
});

test("IMPORT: operação interna (CFOP 5102) zerada → sem finding", () => {
  assert.equal(importFinding(nfeImport({ cfop: "5102" })), undefined);
});

test("IMPORT: exportação (CFOP 7101) zerada → sem finding (imune)", () => {
  assert.equal(importFinding(nfeImport({ cfop: "7101" })), undefined);
});

test("IMPORT: dentro da janela sem penalidades → WARNING", () => {
  const f = importFinding(nfeImport({ cfop: "3102", dhEmi: "2026-05-10T10:00:00-03:00" }));
  assert.equal(f?.severity, "WARNING");
});

test("IMPORT: sem grupo IBSCBS → IMPORT não dispara (coberto por IBSCBS_MISSING)", () => {
  assert.equal(importFinding(nfeImport({ cfop: "3102", noIbscbs: true })), undefined);
});

// ── Item 3: PF_CONTRIB_CNPJ — PF contribuinte deve ter CNPJ (Comunicado CGIBS/RFB 01/2025) ──
// A partir de 01/07/2026 a PF contribuinte de IBS/CBS deve se inscrever no CNPJ e
// não pode emitir por CPF (LC 214 art. 251). Como o enquadramento não é verificável
// do XML, a regra é ALERT informativo: emitente CPF + data ≥ 01/07/2026.

const nfeEmit = (ident: string, dhEmi?: string) => `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod>${dhEmi ? `<dhEmi>${dhEmi}</dhEmi>` : ""}</ide>
  <emit>${ident}<CRT>1</CRT></emit>
  <dest><CPF>11122233344</CPF></dest>
  <det nItem="1"><prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>100.00</vProd></prod>
    <imposto><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib></IBSCBS></imposto></det>
  <total></total>
</infNFe></NFe></nfeProc>`;

const pfFinding = (xml: string, doc: "NFE" | "NFSE" = "NFE") =>
  validateXmlWithRules({ tenantId: "t", documentType: doc, xml }).findings
    .find((f) => f.rule_id === "PF_CONTRIB_CNPJ");

test("PF_CNPJ: emitente CPF + data ≥ 01/07/2026 → ALERT", () => {
  const f = pfFinding(nfeEmit("<CPF>12345678909</CPF>", "2026-07-01T10:00:00-03:00"));
  assert.ok(f, "PF_CONTRIB_CNPJ esperado");
  assert.equal(f!.severity, "ALERT");
  assert.match(f!.recommendation ?? "", /Comunicado Conjunto CGIBS\/RFB/);
});

test("PF_CNPJ: emitente CPF antes de 01/07/2026 → sem finding", () => {
  assert.equal(pfFinding(nfeEmit("<CPF>12345678909</CPF>", "2026-06-30T10:00:00-03:00")), undefined);
});

test("PF_CNPJ: emitente CNPJ (PJ) → sem finding", () => {
  assert.equal(pfFinding(nfeEmit("<CNPJ>12345678000195</CNPJ>", "2026-08-10T10:00:00-03:00")), undefined);
});

test("PF_CNPJ: emitente CPF sem data → sem finding (conservador)", () => {
  assert.equal(pfFinding(nfeEmit("<CPF>12345678909</CPF>")), undefined);
});

test("PF_CNPJ: destinatário CPF mas emitente CNPJ → sem finding (só emitente importa)", () => {
  assert.equal(pfFinding(nfeEmit("<CNPJ>12345678000195</CNPJ>", "2026-09-01T10:00:00-03:00")), undefined);
});

test("PF_CNPJ: NFS-e prestador CPF + DataEmissao ≥ 01/07/2026 → ALERT", () => {
  const xml = `<NFS-e><infNfse>
    <DataEmissao>2026-07-15T10:00:00</DataEmissao>
    <PrestadorServico><RazaoSocial>X</RazaoSocial><CPF>98765432100</CPF></PrestadorServico>
    <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
    <PrestacaoServico><Servico><CodigoServico>123456</CodigoServico><cClassTrib>654321</cClassTrib>
      <CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST></Servico>
      <Valores><BaseCalculo>1000.00</BaseCalculo><AliquotaCBS>0.0010</AliquotaCBS><ValorCBS>1.00</ValorCBS>
      <AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>9.00</ValorIBS></Valores></PrestacaoServico>
  </infNfse></NFS-e>`;
  const f = pfFinding(xml, "NFSE");
  assert.ok(f, "PF_CONTRIB_CNPJ esperado em NFS-e");
  assert.equal(f!.severity, "ALERT");
});

// ── Item #311: códigos de rejeição da NT v1.40 (1115, 1106, 960) ─────────────
// Anota o código oficial SEFAZ na recomendação das detecções que os antecipam
// (NF-e/NFC-e apenas). Precedente: Rejeição 1157 em DPREV_ENTREGA_FRETE.

test("#311: IBSCBS_MISSING (NF-e) cita Rejeição 1115 (UB12-10)", () => {
  const r = validateXmlWithRules({ tenantId: "t", documentType: "NFE",
    xml: nfeAcessoriaErr("3", "2026-09-10T10:00:00-03:00") });
  const f = r.findings.find((f) => f.rule_id === "IBSCBS_MISSING");
  assert.ok(f, "IBSCBS_MISSING esperado");
  assert.match(f!.recommendation ?? "", /Rejeição 1115/);
});

const nfeNoClassTrib = `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide>
  <emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>
  <det nItem="1"><prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>
    <imposto><IBSCBS><CST>000</CST></IBSCBS></imposto></det>
  <total></total>
</infNFe></NFe></nfeProc>`;

test("#311: CCLASSTRIB_6_DIGITS (NF-e) cita Rejeição 1106 e 960", () => {
  const r = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml: nfeNoClassTrib });
  const f = r.findings.find((f) => f.rule_id === "CCLASSTRIB_6_DIGITS");
  assert.ok(f, "CCLASSTRIB_6_DIGITS esperado");
  assert.match(f!.recommendation ?? "", /1106/);
  assert.match(f!.recommendation ?? "", /960/);
});

test("#311: NFS-e NÃO recebe código de rejeição NF-e (1106)", () => {
  const xml = `<NFS-e><infNfse>
    <PrestadorServico><RazaoSocial>X</RazaoSocial></PrestadorServico>
    <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
    <PrestacaoServico><Servico><CodigoServico>123456</CodigoServico>
      <CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST></Servico>
      <Valores><BaseCalculo>1000.00</BaseCalculo><AliquotaCBS>0.0010</AliquotaCBS><ValorCBS>1.00</ValorCBS>
      <AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>9.00</ValorIBS></Valores></PrestacaoServico>
  </infNfse></NFS-e>`;
  const r = validateXmlWithRules({ tenantId: "t", documentType: "NFSE", xml });
  const f = r.findings.find((f) => f.rule_id === "CCLASSTRIB_6_DIGITS");
  assert.ok(f, "CCLASSTRIB_6_DIGITS esperado em NFS-e");
  assert.doesNotMatch(f!.recommendation ?? "", /1106/);
});

// ── #312 — DEVOLUCAO_DFEREF (devolução referencia nota original por item) ─────
function devNfe(fin: string, dhEmi: string, nItems: number, nRef: number): string {
  const dets = Array.from({ length: nItems }, (_, i) =>
    `<det nItem="${i + 1}"><prod><NCM>84713012</NCM><vProd>10.00</vProd></prod></det>`).join("");
  const refs = Array.from({ length: nRef }, () =>
    "<DFeReferenciado><refNFe>35260612345678000195550010000000011000000017</refNFe></DFeReferenciado>").join("");
  return `<nfeProc><NFe><infNFe><ide><mod>55</mod><finNFe>${fin}</finNFe>` +
    `<dhEmi>${dhEmi}T10:00:00-03:00</dhEmi></ide>` +
    `<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>${refs}${dets}` +
    `</infNFe></NFe></nfeProc>`;
}
function devFindings(xml: string, pedagogicalMode = false) {
  return validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml, pedagogicalMode })
    .findings.filter((f) => f.rule_id === "DEVOLUCAO_DFEREF");
}

test("#312 devolução sem DFeReferenciado após 01/09 → FATAL", () => {
  const f = devFindings(devNfe("4", "2026-09-15", 1, 0));
  assert.ok(f.some((x) => x.id === "F_DEVOLUCAO_DFEREF" && x.severity === "FATAL"));
});

test("#312 devolução sem DFeReferenciado antes da vigência → WARNING", () => {
  const f = devFindings(devNfe("4", "2026-08-15", 1, 0));
  assert.ok(f.length > 0 && f.every((x) => x.severity === "WARNING"));
});

test("#312 devolução com DFeReferenciado por item → sem finding", () => {
  assert.equal(devFindings(devNfe("4", "2026-09-15", 2, 2)).length, 0);
});

test("#312 referência parcial → finding", () => {
  assert.ok(devFindings(devNfe("4", "2026-09-15", 2, 1)).length > 0);
});

test("#312 não-devolução (finNFe=1) → sem finding", () => {
  assert.equal(devFindings(devNfe("1", "2026-09-15", 1, 0)).length, 0);
});

test("#312 pedagogicalMode mantém WARNING após vigência", () => {
  const f = devFindings(devNfe("4", "2026-09-15", 1, 0), true);
  assert.ok(f.length > 0 && f.every((x) => x.severity === "WARNING"));
});

// ── #314 — Imposto Seletivo (IS_CALC + IS_EXPECTED) ──────────────────────────
function isNfe(ncm: string, opts: { vbcis?: string; pis?: string; vis?: string; pespec?: string; qtrib?: string } = {}): string {
  let grp = "";
  if (opts.vis !== undefined) {
    let f = "";
    if (opts.vbcis !== undefined) f += `<vBCIS>${opts.vbcis}</vBCIS>`;
    if (opts.pis !== undefined) f += `<pIS>${opts.pis}</pIS>`;
    if (opts.pespec !== undefined) f += `<pISEspec>${opts.pespec}</pISEspec>`;
    if (opts.qtrib !== undefined) f += `<qTrib>${opts.qtrib}</qTrib>`;
    f += `<vIS>${opts.vis}</vIS>`;
    grp = `<IS><CSTIS>01</CSTIS><cClassTribIS>000001</cClassTribIS><gIS>${f}</gIS></IS>`;
  }
  return `<nfeProc><NFe><infNFe><ide><mod>55</mod></ide>` +
    `<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>` +
    `<det nItem="1"><prod><NCM>${ncm}</NCM><vProd>1000.00</vProd></prod>` +
    `<imposto>${grp}</imposto></det></infNFe></NFe></nfeProc>`;
}
function isFindings(xml: string, rule: string) {
  return validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml }).findings.filter((f) => f.rule_id === rule);
}

test("#314 IS ad valorem coerente → sem IS_CALC", () => {
  assert.equal(isFindings(isNfe("22030000", { vbcis: "1000.00", pis: "0.1000", vis: "100.00" }), "IS_CALC").length, 0);
});

test("#314 IS incoerente → IS_CALC FATAL", () => {
  const f = isFindings(isNfe("22030000", { vbcis: "1000.00", pis: "0.1000", vis: "50.00" }), "IS_CALC");
  assert.ok(f.some((x) => x.id === "F_IS_CALC" && x.severity === "FATAL"));
});

test("#314 IS específico coerente → sem IS_CALC", () => {
  assert.equal(isFindings(isNfe("24022000", { qtrib: "100", pespec: "0.50", vis: "50.00" }), "IS_CALC").length, 0);
});

test("#314 NCM bebida/fumo sem grupo IS → IS_EXPECTED ALERT", () => {
  const f = isFindings(isNfe("22030000"), "IS_EXPECTED");
  assert.ok(f.some((x) => x.id === "F_IS_EXPECTED" && x.severity === "ALERT"));
});

test("#314 NCM não sujeito → sem IS_EXPECTED", () => {
  assert.equal(isFindings(isNfe("84713012"), "IS_EXPECTED").length, 0);
});

test("#314 NCM sujeito com grupo IS → sem IS_EXPECTED", () => {
  assert.equal(isFindings(isNfe("22030000", { vbcis: "1000.00", pis: "0.1000", vis: "100.00" }), "IS_EXPECTED").length, 0);
});

// ── #311 — SUFRAMA_DV (C22-20) + ALCZFM_NPROC (UB66c-10) ─────────────────────
function sufNfe(opts: { isuf?: string; alczfm?: string } = {}): string {
  const isuf = opts.isuf !== undefined ? `<ISUFemit>${opts.isuf}</ISUFemit>` : "";
  const alc = opts.alczfm ?? "";
  return `<nfeProc><NFe><infNFe><ide><mod>55</mod></ide>` +
    `<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT>${isuf}</emit>` +
    `<det nItem="1"><prod><NCM>84713012</NCM><vProd>1000.00</vProd></prod>` +
    `<imposto><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib>${alc}</IBSCBS></imposto></det>` +
    `</infNFe></NFe></nfeProc>`;
}
function sufFindings(xml: string, rule: string) {
  return validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml }).findings.filter((f) => f.rule_id === rule);
}

test("#311 SUFRAMA_DV: DV válido (100123457) → sem finding", () => {
  assert.equal(sufFindings(sufNfe({ isuf: "100123457" }), "SUFRAMA_DV").length, 0);
});

test("#311 SUFRAMA_DV: DV inválido → WARNING (C22-20)", () => {
  const f = sufFindings(sufNfe({ isuf: "100123450" }), "SUFRAMA_DV");
  assert.ok(f.some((x) => x.id === "F_SUFRAMA_DV" && x.severity === "WARNING"));
});

test("#311 SUFRAMA_DV: sem ISUFemit → sem finding", () => {
  assert.equal(sufFindings(sufNfe(), "SUFRAMA_DV").length, 0);
});

test("#311 ALCZFM_NPROC: grupo com nProcSuframa → sem finding", () => {
  const xml = sufNfe({ alczfm: "<gALCZFMCBS><nProcSuframa>1234567890</nProcSuframa></gALCZFMCBS>" });
  assert.equal(sufFindings(xml, "ALCZFM_NPROC").length, 0);
});

test("#311 ALCZFM_NPROC: grupo sem nProcSuframa → WARNING (UB66c-10)", () => {
  const f = sufFindings(sufNfe({ alczfm: "<gALCZFMCBS><vCBS>0.00</vCBS></gALCZFMCBS>" }), "ALCZFM_NPROC");
  assert.ok(f.some((x) => x.id === "F_ALCZFM_NPROC" && x.severity === "WARNING"));
});

test("#311 ALCZFM_NPROC: sem grupo → sem finding", () => {
  assert.equal(sufFindings(sufNfe(), "ALCZFM_NPROC").length, 0);
});

// ── #311 — CINDOP_NFCE (B25d: cIndOp não permitido em NFC-e) ──────────────────
function cindopDoc(model: string, withCindop: boolean): string {
  const c = withCindop ? "<cIndOp>010104</cIndOp>" : "";
  return `<nfeProc><NFe><infNFe><ide><mod>${model}</mod></ide>` +
    `<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>` +
    `<det nItem="1"><prod><NCM>84713012</NCM>${c}<vProd>10.00</vProd></prod>` +
    `<imposto><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib></IBSCBS></imposto></det>` +
    `</infNFe></NFe></nfeProc>`;
}

test("#311 CINDOP_NFCE: cIndOp em NFC-e (mod 65) → WARNING", () => {
  const f = validateXmlWithRules({ tenantId: "t", documentType: "NFCE", xml: cindopDoc("65", true) })
    .findings.filter((x) => x.rule_id === "CINDOP_NFCE");
  assert.ok(f.some((x) => x.id === "F_CINDOP_NFCE" && x.severity === "WARNING"));
});

test("#311 CINDOP_NFCE: cIndOp em NF-e (mod 55) → sem finding", () => {
  const f = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml: cindopDoc("55", true) })
    .findings.filter((x) => x.rule_id === "CINDOP_NFCE");
  assert.equal(f.length, 0);
});

test("#311 CINDOP_NFCE: NFC-e sem cIndOp → sem finding", () => {
  const f = validateXmlWithRules({ tenantId: "t", documentType: "NFCE", xml: cindopDoc("65", false) })
    .findings.filter((x) => x.rule_id === "CINDOP_NFCE");
  assert.equal(f.length, 0);
});

// ── #311 — RETIRADA_CINDOP (B25d-30) + ALCZFM_CBS_CALC (UB66e-10) ────────────
function b25Nfe(opts: { cindop?: string; retirada?: boolean; alc?: string } = {}): string {
  const cind = opts.cindop ? `<cIndOp>${opts.cindop}</cIndOp>` : "";
  const ret = opts.retirada ? "<retirada><xLgr>Rua X</xLgr></retirada>" : "";
  const alc = opts.alc ?? "";
  return `<nfeProc><NFe><infNFe><ide><mod>55</mod></ide>` +
    `<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>${cind}${ret}` +
    `<det nItem="1"><prod><NCM>84713012</NCM><vProd>1000.00</vProd></prod>` +
    `<imposto><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib>` +
    `<gIBSCBS><vBC>1000.00</vBC></gIBSCBS>${alc}</IBSCBS></imposto></det>` +
    `</infNFe></NFe></nfeProc>`;
}
function b25Find(xml: string, rule: string) {
  return validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml }).findings.filter((f) => f.rule_id === rule);
}
const ALC = (v: string) => `<gALCZFMCBS><tpALCZFMCBS>2</tpALCZFMCBS><nProcSuframa>1234567890</nProcSuframa><pAliqEfetRegCBS>8.80</pAliqEfetRegCBS><vTribRegCBS>${v}</vTribRegCBS></gALCZFMCBS>`;

test("#311 RETIRADA_CINDOP: cIndOp 010104 sem retirada → WARNING (1110)", () => {
  const f = b25Find(b25Nfe({ cindop: "010104", retirada: false }), "RETIRADA_CINDOP");
  assert.ok(f.some((x) => x.id === "F_RETIRADA_CINDOP" && x.severity === "WARNING"));
});

test("#311 RETIRADA_CINDOP: com retirada → sem finding", () => {
  assert.equal(b25Find(b25Nfe({ cindop: "010105", retirada: true }), "RETIRADA_CINDOP").length, 0);
});

test("#311 RETIRADA_CINDOP: cIndOp de outro valor → sem finding", () => {
  assert.equal(b25Find(b25Nfe({ cindop: "000000" }), "RETIRADA_CINDOP").length, 0);
});

test("#311 ALCZFM_CBS_CALC: vTribRegCBS coerente (88.00) → sem finding", () => {
  assert.equal(b25Find(b25Nfe({ alc: ALC("88.00") }), "ALCZFM_CBS_CALC").length, 0);
});

test("#311 ALCZFM_CBS_CALC: vTribRegCBS incoerente → WARNING (1218)", () => {
  const f = b25Find(b25Nfe({ alc: ALC("50.00") }), "ALCZFM_CBS_CALC");
  assert.ok(f.some((x) => x.id === "F_ALCZFM_CBS_CALC" && x.severity === "WARNING"));
});

// ── #403: Grupo W03 (IBSCBSTot) — NT 2025.002-RTC v1.40, W34-10/W34-20 ───────
// SEFAZ rejeita em produção a partir de 03/08/2026 (CRT 3) / 04/01/2027 (Simples/MEI):
//   W34-20 → Rejeição 1119: IBSCBSTot ausente com item informando IBS/CBS;
//   W34-10 → Rejeição 1118: IBSCBSTot informado sem nenhum item com IBS/CBS.

const w03Item = `<det nItem="1">
    <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>
    <imposto>
      <IBSCBS>
        <CST>000</CST>
        <cClassTrib>000001</cClassTrib>
        <gIBSCBS>
          <vBC>1000.00</vBC>
          <gIBSUF><pIBSUF>0.0005</pIBSUF><vIBSUF>0.50</vIBSUF></gIBSUF>
          <gIBSMun><pIBSMun>0.0005</pIBSMun><vIBSMun>0.50</vIBSMun></gIBSMun>
          <vIBS>1.00</vIBS>
          <gCBS><pCBS>0.0090</pCBS><vCBS>9.00</vCBS></gCBS>
        </gIBSCBS>
      </IBSCBS>
    </imposto>
  </det>`;

const nfeW03 = (opts: { crt: string; dhEmi: string; item?: boolean; tot?: boolean }) => `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod><dhEmi>${opts.dhEmi}</dhEmi></ide>
  <emit><CNPJ>12345678000195</CNPJ><CRT>${opts.crt}</CRT></emit>
  ${opts.item === false ? `<det nItem="1"><prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod><imposto><ICMS><ICMS00><CST>00</CST></ICMS00></ICMS></imposto></det>` : w03Item}
  <total>${opts.tot === false ? "" : "<IBSCBSTot><vBCIBSCBS>1000.00</vBCIBSCBS><vIBS>1.00</vIBS><vCBS>9.00</vCBS></IBSCBSTot>"}</total>
</infNFe></NFe></nfeProc>`;

test("#403 IBSCBSTOT_MISSING: CRT 3, item com IBSCBS sem IBSCBSTot (pós 01/08) → FATAL citando 1119", () => {
  const xml = nfeW03({ crt: "3", dhEmi: "2026-08-10T10:00:00-03:00", tot: false });
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "IBSCBSTOT_MISSING");
  assert.ok(f, "IBSCBSTOT_MISSING esperado");
  assert.equal(f!.severity, "FATAL");
  assert.ok(f!.recommendation?.includes("1119"), "recommendation deve citar Rejeição 1119");
  assert.ok(f!.recommendation?.includes("W34-20"), "recommendation deve citar regra W34-20");
});

test("#403 IBSCBSTOT_MISSING: CRT 1 (Simples) → WARNING (faseamento 04/01/2027)", () => {
  const xml = nfeW03({ crt: "1", dhEmi: "2026-08-10T10:00:00-03:00", tot: false });
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "IBSCBSTOT_MISSING");
  assert.ok(f, "IBSCBSTOT_MISSING esperado");
  assert.equal(f!.severity, "WARNING");
});

test("#403 IBSCBSTOT_MISSING: dhEmi na janela sem penalidades (até 31/07/2026) → WARNING com nota do Ato Conjunto", () => {
  const xml = nfeW03({ crt: "3", dhEmi: "2026-07-10T10:00:00-03:00", tot: false });
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "IBSCBSTOT_MISSING");
  assert.ok(f, "IBSCBSTOT_MISSING esperado");
  assert.equal(f!.severity, "WARNING");
  assert.ok(f!.recommendation?.includes("Ato Conjunto"), "deve citar a janela do Ato Conjunto 1/25");
});

test("#403 IBSCBSTOT_UNDUE: IBSCBSTot presente sem item com IBS/CBS → FATAL citando 1118", () => {
  const xml = nfeW03({ crt: "3", dhEmi: "2026-08-10T10:00:00-03:00", item: false });
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "IBSCBSTOT_UNDUE");
  assert.ok(f, "IBSCBSTOT_UNDUE esperado");
  assert.equal(f!.severity, "FATAL");
  assert.ok(f!.recommendation?.includes("1118"), "recommendation deve citar Rejeição 1118");
});

test("#403 W03 coerente (item + IBSCBSTot) → sem findings W03", () => {
  const xml = nfeW03({ crt: "3", dhEmi: "2026-08-10T10:00:00-03:00" });
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  assert.equal(result.findings.find((f) => f.rule_id === "IBSCBSTOT_MISSING"), undefined);
  assert.equal(result.findings.find((f) => f.rule_id === "IBSCBSTOT_UNDUE"), undefined);
});

test("#403 IBSCBS_TOTAL: recommendation cita códigos oficiais W56-10/1091 e W47-10/1085", () => {
  const xml = nfeW03({ crt: "3", dhEmi: "2026-08-10T10:00:00-03:00" }).replace(
    "<IBSCBSTot><vBCIBSCBS>1000.00</vBCIBSCBS><vIBS>1.00</vIBS><vCBS>9.00</vCBS></IBSCBSTot>",
    "<IBSCBSTot><vBCIBSCBS>1000.00</vBCIBSCBS><vIBS>1.00</vIBS><vCBS>99.00</vCBS></IBSCBSTot>",
  );
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFE", xml });
  const f = result.findings.find((f) => f.rule_id === "IBSCBS_TOTAL");
  assert.ok(f, "IBSCBS_TOTAL esperado (total CBS divergente)");
  assert.ok(f!.recommendation?.includes("1091"), "recommendation deve citar Rejeição 1091");
});

// ── #406 — NT 007/2026 (SE/CGNFS-e): indZFMALC + vPis/vCofins devidos ────────
// 3 fixtures conforme DoD: serviço comum (caminho feliz), locação de imóvel
// (nova operação documentável) e operação ZFM (indZFMALC).

const NFSE_SERVICO_COMUM = `<NFS-e><infNfse>
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
      <AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>90.00</ValorIBS>
    </Valores>
  </PrestacaoServico>
</infNfse></NFS-e>`;

const NFSE_LOCACAO_IMOVEL = `<NFS-e><infNfse>
  <PrestadorServico><RazaoSocial>Imobiliária Z</RazaoSocial></PrestadorServico>
  <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
  <PrestacaoServico>
    <Servico>
      <TipoOperacao>LOCACAO_IMOVEL</TipoOperacao>
      <CodigoServico>310101</CodigoServico>
      <cClassTrib>654321</cClassTrib>
      <CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST>
    </Servico>
    <Valores>
      <BaseCalculo>5000.00</BaseCalculo>
      <AliquotaCBS>0.0010</AliquotaCBS><ValorCBS>5.00</ValorCBS>
      <AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>45.00</ValorIBS>
      <ValorPis>1.65</ValorPis><ValorCofins>7.60</ValorCofins>
    </Valores>
  </PrestacaoServico>
</infNfse></NFS-e>`;

function nfseZfm(valorCbs: string): string {
  return `<NFS-e><infNfse>
    <PrestadorServico><RazaoSocial>Distribuidora ZFM</RazaoSocial></PrestadorServico>
    <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
    <PrestacaoServico>
      <Servico>
        <CodigoServico>123456</CodigoServico>
        <cClassTrib>654321</cClassTrib>
        <CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST>
      </Servico>
      <Valores>
        <IndZFMALC>1</IndZFMALC>
        <BaseCalculo>10000.00</BaseCalculo>
        <AliquotaCBS>0.0000</AliquotaCBS><ValorCBS>${valorCbs}</ValorCBS>
        <AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>90.00</ValorIBS>
      </Valores>
    </PrestacaoServico>
  </infNfse></NFS-e>`;
}

function nfseFindings(xml: string, rule: string) {
  return validateXmlWithRules({ tenantId: "t", documentType: "NFSE", xml }).findings.filter((f) => f.rule_id === rule);
}

test("#406 serviço comum: caminho feliz, sem findings novos", () => {
  assert.equal(nfseFindings(NFSE_SERVICO_COMUM, "INDZFMALC_CBS_ZERO").length, 0);
  assert.equal(nfseFindings(NFSE_SERVICO_COMUM, "PIS_COFINS_DEVIDO_NEGATIVO").length, 0);
});

test("#406 locação de imóvel: nova operação documentável não quebra o parser", () => {
  const result = validateXmlWithRules({ tenantId: "t", documentType: "NFSE", xml: NFSE_LOCACAO_IMOVEL });
  const fatals = result.findings.filter((f) => f.severity === "FATAL");
  assert.deepEqual(fatals.map((f) => f.rule_id), []);
  assert.equal(nfseFindings(NFSE_LOCACAO_IMOVEL, "PIS_COFINS_DEVIDO_NEGATIVO").length, 0);
});

test("#406 INDZFMALC_CBS_ZERO: ZFM com CBS zero → sem finding", () => {
  assert.equal(nfseFindings(nfseZfm("0.00"), "INDZFMALC_CBS_ZERO").length, 0);
});

test("#406 INDZFMALC_CBS_ZERO: ZFM com CBS > 0 → WARNING", () => {
  const f = nfseFindings(nfseZfm("10.00"), "INDZFMALC_CBS_ZERO");
  assert.ok(f.some((x) => x.id === "F_INDZFMALC_CBS_ZERO" && x.severity === "WARNING"));
});

test("#406 PIS_COFINS_DEVIDO_NEGATIVO: vPis negativo → WARNING", () => {
  const xml = NFSE_SERVICO_COMUM.replace("</Valores>", "<ValorPis>-5.00</ValorPis></Valores>");
  const f = nfseFindings(xml, "PIS_COFINS_DEVIDO_NEGATIVO");
  assert.ok(f.some((x) => x.id === "F_PIS_COFINS_DEVIDO_NEGATIVO_PIS" && x.severity === "WARNING"));
});

test("#406 PIS_COFINS_DEVIDO_NEGATIVO: vCofins negativo → WARNING", () => {
  const xml = NFSE_SERVICO_COMUM.replace("</Valores>", "<ValorCofins>-3.00</ValorCofins></Valores>");
  const f = nfseFindings(xml, "PIS_COFINS_DEVIDO_NEGATIVO");
  assert.ok(f.some((x) => x.id === "F_PIS_COFINS_DEVIDO_NEGATIVO_COFINS" && x.severity === "WARNING"));
});

test("#406 PIS_COFINS_DEVIDO_NEGATIVO: valores positivos (locação) → sem finding", () => {
  assert.equal(nfseFindings(NFSE_LOCACAO_IMOVEL, "PIS_COFINS_DEVIDO_NEGATIVO").length, 0);
});

// ── #480 — PIS_COFINS_DEVIDO_CALC: vPis/vCofins = base × alíquota ────────────
// Fixture com os valores do exemplo oficial (manual de integração NFS-e
// pós-NT007/2026): vBCPisCofins=988.33, pAliqPis=1.65%, pAliqCofins=7.60%
// → vPis=16.31, vCofins=75.11 (bate exato, arredondamento bancário).

function nfsePisCofinsCalc(vPis: string, vCofins: string): string {
  return NFSE_SERVICO_COMUM.replace(
    "</Valores>",
    `<vBCPisCofins>988.33</vBCPisCofins><pAliqPis>1.65</pAliqPis><pAliqCofins>7.60</pAliqCofins>` +
      `<vPis>${vPis}</vPis><vCofins>${vCofins}</vCofins></Valores>`,
  );
}

test("#480 PIS_COFINS_DEVIDO_CALC: valores corretos → sem finding", () => {
  assert.equal(nfseFindings(nfsePisCofinsCalc("16.31", "75.11"), "PIS_COFINS_DEVIDO_CALC").length, 0);
});

test("#480 PIS_COFINS_DEVIDO_CALC: vPis divergente → WARNING", () => {
  const f = nfseFindings(nfsePisCofinsCalc("20.00", "75.11"), "PIS_COFINS_DEVIDO_CALC");
  assert.ok(f.some((x) => x.id === "F_PIS_COFINS_DEVIDO_CALC_PIS" && x.severity === "WARNING"));
});

test("#480 PIS_COFINS_DEVIDO_CALC: vCofins divergente → WARNING", () => {
  const f = nfseFindings(nfsePisCofinsCalc("16.31", "80.00"), "PIS_COFINS_DEVIDO_CALC");
  assert.ok(f.some((x) => x.id === "F_PIS_COFINS_DEVIDO_CALC_COFINS" && x.severity === "WARNING"));
});

test("#480 PIS_COFINS_DEVIDO_CALC: sem base/alíquota → regra não dispara", () => {
  // Campos opcionais — NFSE_LOCACAO_IMOVEL já tem ValorPis/ValorCofins sem
  // vBCPisCofins/pAliqPis/pAliqCofins (degradação graciosa, mesmo padrão do IBSCBS_CALC).
  assert.equal(nfseFindings(NFSE_LOCACAO_IMOVEL, "PIS_COFINS_DEVIDO_CALC").length, 0);
});

// ── #405 — DANFE Simplificado Tipo 2 (tpImp=6, NT 2026.002 v1.00) ────────────
function danfeT2Nfe(opts: {
  tpImp?: string; tpNf?: string; idDest?: string; finNFe?: string; nfref?: boolean; dhEmi?: string; mod?: string; cfop?: string;
} = {}): string {
  const { tpImp = "6", tpNf = "1", idDest = "1", finNFe = "1", nfref = false, dhEmi = "2026-06-01", mod = "55", cfop = "5102" } = opts;
  const ref = nfref ? "<NFref><refNFe>35260612345678000195550010000000011000000017</refNFe></NFref>" : "";
  return `<nfeProc><NFe><infNFe><ide><mod>${mod}</mod><tpImp>${tpImp}</tpImp><tpNF>${tpNf}</tpNF>` +
    `<idDest>${idDest}</idDest><finNFe>${finNFe}</finNFe><dhEmi>${dhEmi}T10:00:00-03:00</dhEmi>${ref}</ide>` +
    `<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>` +
    `<det nItem="1"><prod><CFOP>${cfop}</CFOP><NCM>84713012</NCM><vProd>10.00</vProd></prod></det>` +
    `</infNFe></NFe></nfeProc>`;
}
function danfeT2Findings(xml: string, documentType: "NFE" | "NFCE" = "NFE", pedagogicalMode = false) {
  return validateXmlWithRules({ tenantId: "t", documentType, xml, pedagogicalMode })
    .findings.filter((f) => f.rule_id === "DANFE_SIMPLIFICADO_RESTRICAO");
}
function danfeT2CfopFindings(xml: string, documentType: "NFE" | "NFCE" = "NFE", pedagogicalMode = false) {
  return validateXmlWithRules({ tenantId: "t", documentType, xml, pedagogicalMode })
    .findings.filter((f) => f.rule_id === "DANFE_SIMPLIFICADO_CFOP");
}

test("#405 DANFE T2 compliant (saída/interna/normal/sem NFref) → sem finding", () => {
  assert.equal(danfeT2Findings(danfeT2Nfe()).length, 0);
});

test("#405 DANFE T2 entrada (tpNF=0) → Rejeição 706", () => {
  const f = danfeT2Findings(danfeT2Nfe({ tpNf: "0" }));
  assert.ok(f.some((x) => x.id === "F_DANFE_T2_ENTRADA" && x.recommendation.includes("706")));
});

test("#405 DANFE T2 interestadual (idDest=2) → Rejeição 707", () => {
  const f = danfeT2Findings(danfeT2Nfe({ idDest: "2" }));
  assert.ok(f.some((x) => x.id === "F_DANFE_T2_INTERESTADUAL" && x.recommendation.includes("707")));
});

test("#405 DANFE T2 com NFref → Rejeição 708", () => {
  const f = danfeT2Findings(danfeT2Nfe({ nfref: true }));
  assert.ok(f.some((x) => x.id === "F_DANFE_T2_NFREF" && x.recommendation.includes("708")));
});

test("#405 DANFE T2 finalidade não normal (finNFe=2) → Rejeição 715", () => {
  const f = danfeT2Findings(danfeT2Nfe({ finNFe: "2" }));
  assert.ok(f.some((x) => x.id === "F_DANFE_T2_FINALIDADE" && x.recommendation.includes("715")));
});

test("#405 tpImp≠6 → regra não dispara mesmo com violações", () => {
  assert.equal(danfeT2Findings(danfeT2Nfe({ tpImp: "1", tpNf: "0", idDest: "2", nfref: true, finNFe: "2" })).length, 0);
});

test("#405 NFC-e (modelo 65) → regra não se aplica", () => {
  assert.equal(danfeT2Findings(danfeT2Nfe({ tpNf: "0", mod: "65" }), "NFCE").length, 0);
});

test("#405 antes da vigência (03/08/2026) → WARNING", () => {
  const f = danfeT2Findings(danfeT2Nfe({ tpNf: "0", dhEmi: "2026-07-15" }));
  assert.ok(f.length > 0 && f.every((x) => x.severity === "WARNING"));
});

test("#405 após a vigência → FATAL", () => {
  const f = danfeT2Findings(danfeT2Nfe({ tpNf: "0", dhEmi: "2026-08-10" }));
  assert.ok(f.some((x) => x.id === "F_DANFE_T2_ENTRADA" && x.severity === "FATAL"));
});

test("#405 pedagogicalMode mantém WARNING após a vigência", () => {
  const f = danfeT2Findings(danfeT2Nfe({ tpNf: "0", dhEmi: "2026-08-10" }), "NFE", true);
  assert.ok(f.length > 0 && f.every((x) => x.severity === "WARNING"));
});

test("#405 múltiplas violações geram múltiplos findings", () => {
  const f = danfeT2Findings(danfeT2Nfe({ tpNf: "0", idDest: "2", nfref: true, finNFe: "4" }));
  const ids = new Set(f.map((x) => x.id));
  assert.deepEqual(ids, new Set(["F_DANFE_T2_ENTRADA", "F_DANFE_T2_INTERESTADUAL", "F_DANFE_T2_NFREF", "F_DANFE_T2_FINALIDADE"]));
});

// ── #482 — DANFE_SIMPLIFICADO_CFOP: allowlist de CFOP (I08-150, Rejeição 725) ─
// Mesmo código de "CFOP inválido" já usado pela SEFAZ para NFC-e, reaproveitado
// para NF-e+tpImp=6. Confirmado via fórum SPED Brasil + doc. Senior (2026-07-20).

test("#482 CFOP permitido → sem finding", () => {
  assert.equal(danfeT2CfopFindings(danfeT2Nfe({ cfop: "5102" })).length, 0);
});

test("#482 CFOP fora do allowlist → Rejeição 725", () => {
  const f = danfeT2CfopFindings(danfeT2Nfe({ cfop: "5949" }));
  assert.ok(f.some((x) => x.id === "F_DANFE_T2_CFOP" && x.recommendation.includes("725") && x.title.includes("5949")));
});

test("#482 CFOP 5910 permitido (único CFOP extra vs. allowlist da Rejeição 725 de NFC-e)", () => {
  assert.equal(danfeT2CfopFindings(danfeT2Nfe({ cfop: "5910" })).length, 0);
});

test("#482 tpImp≠6 → regra CFOP não dispara", () => {
  assert.equal(danfeT2CfopFindings(danfeT2Nfe({ tpImp: "1", cfop: "5949" })).length, 0);
});

test("#482 CFOP inválido antes da vigência (03/08/2026) → WARNING", () => {
  const f = danfeT2CfopFindings(danfeT2Nfe({ cfop: "5949", dhEmi: "2026-07-15" }));
  assert.ok(f.length > 0 && f.every((x) => x.severity === "WARNING"));
});

test("#482 CFOP inválido após a vigência → FATAL", () => {
  const f = danfeT2CfopFindings(danfeT2Nfe({ cfop: "5949", dhEmi: "2026-08-10" }));
  assert.ok(f.some((x) => x.id === "F_DANFE_T2_CFOP" && x.severity === "FATAL"));
});
