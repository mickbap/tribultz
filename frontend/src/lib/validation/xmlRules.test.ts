import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { validateXmlWithRules } from "./xmlRules";

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
  // Original 3 format rules + IBSCBS_MISSING + CEST_MISSING + LAYOUT_PORTAL
  assert.ok(fatalIds.includes("CST_3_DIGITS"), "expected CST_3_DIGITS");
  assert.ok(fatalIds.includes("CCLASSTRIB_6_DIGITS"), "expected CCLASSTRIB_6_DIGITS");
  assert.ok(fatalIds.includes("SERVICE_CODE_6_DIGITS"), "expected SERVICE_CODE_6_DIGITS");
  assert.ok(fatalIds.includes("IBSCBS_MISSING"), "expected IBSCBS_MISSING");
  assert.ok(fatalIds.includes("CEST_MISSING"), "expected CEST_MISSING");
  assert.ok(fatalIds.includes("LAYOUT_PORTAL"), "expected LAYOUT_PORTAL");
  assert.equal(fatalIds.length, 6);
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

test("CEST_MISSING: nota sem CEST gera FATAL", () => {
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
  assert.equal(f!.severity, "FATAL");
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
