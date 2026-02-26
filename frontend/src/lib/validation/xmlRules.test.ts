import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { validateXmlWithRules } from "./xmlRules";

function fixture(name: string): string {
  return readFileSync(join(process.cwd(), "src/lib/validation/fixtures", name), "utf-8");
}

test("NFSe com erros gera findings FATAL esperados", () => {
  const result = validateXmlWithRules({
    tenantId: "tenant-a",
    documentType: "NFSE",
    xml: fixture("nfse-com-erros.xml"),
  });

  const ids = result.findings.map((f) => f.id);
  assert.deepEqual(ids.slice(0, 3), ["F_CST_LEN", "F_CCLASSTRIB_LEN", "F_SERVICE_CODE_LEN"]);
  assert.equal(result.findings.filter((f) => f.severity === "FATAL").length, 3);
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
