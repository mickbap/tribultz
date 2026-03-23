import assert from "node:assert/strict";
import test from "node:test";
import { buildAuditableReportCsv, buildAuditableReportHtml } from "./auditableReport";
import type { ValidationResultV11 } from "../types";

const FIXED_DATE = new Date("2026-03-22T10:00:00.000Z");

function makeResult(): ValidationResultV11 {
  return {
    job: { id: "job_xml_abc123", created_at: "2026-03-22T09:00:00.000Z", tenant_id: "tenant-demo" },
    audit: {
      id: "audit_xml_abc123",
      job_id: "job_xml_abc123",
      events: [
        {
          id: "evt_abc123_created",
          action: "xml_validation_started",
          created_at: "2026-03-22T09:00:00.000Z",
          payload: { document_type: "NFSE", findings_total: 3, fatals: 1 },
        },
      ],
    },
    findings: [
      {
        id: "F_CST_LEN",
        severity: "FATAL",
        rule_id: "CST_3_DIGITS",
        title: "CST invalido (esperado 3 digitos)",
        where: { field: "CST", xpath: "/NFS-e/infNfse//CST", snippet: "<CST>12</CST>" },
        recommendation: "Corrigir no ERP e reemitir.",
        evidence_ids: ["E_XML_CST_LEN"],
      },
      {
        id: "A_NCM_REVIEW",
        severity: "ALERT",
        rule_id: "NCM_PLACEHOLDER",
        title: "Revisar NCM conforme classificacao fiscal vigente",
        where: { field: "NCM", xpath: "/NFS-e/infNfse//NCM", snippet: "<NCM>12345678</NCM>" },
        recommendation: "Conferir classificacao fiscal.",
        evidence_ids: ["E_XML_NCM_INFO"],
      },
    ],
    evidences: [
      { id: "E_XML_CST_LEN", type: "xml", label: "Trecho XML — CST", xpath: "/NFS-e/infNfse//CST", snippet: "<CST>12</CST>" },
      { id: "E_XML_NCM_INFO", type: "xml", label: "NCM (avaliacao informativa)", xpath: "/NFS-e/infNfse//NCM", snippet: "<NCM>12345678</NCM>" },
    ],
  };
}

// ── CSV tests ──────────────────────────────────────────────────

test("CSV contém header de metadados com job_id e contagens", () => {
  const csv = buildAuditableReportCsv(makeResult(), "NFSE", FIXED_DATE);
  assert.match(csv, /# job_id: job_xml_abc123/);
  assert.match(csv, /# total_findings: 2/);
  assert.match(csv, /# fatal_count: 1/);
  assert.match(csv, /# alert_count: 1/);
});

test("CSV contém linha de cabeçalho com colunas esperadas", () => {
  const csv = buildAuditableReportCsv(makeResult(), "NFSE", FIXED_DATE);
  const lines = csv.split("\n").filter((l) => !l.startsWith("#") && l.trim() !== "");
  const header = lines[0];
  assert.ok(header.includes("finding_id"));
  assert.ok(header.includes("severity"));
  assert.ok(header.includes("rule_id"));
  assert.ok(header.includes("recommendation"));
  assert.ok(header.includes("evidence_ids"));
});

test("CSV contém uma linha por finding", () => {
  const csv = buildAuditableReportCsv(makeResult(), "NFSE", FIXED_DATE);
  const dataLines = csv.split("\n").filter((l) => !l.startsWith("#") && l.trim() !== "");
  // 1 header + 2 data rows
  assert.equal(dataLines.length, 3);
});

test("CSV escapa campos com virgula corretamente", () => {
  const result = makeResult();
  result.findings[0].title = "Campo com, virgula";
  const csv = buildAuditableReportCsv(result, "NFSE", FIXED_DATE);
  assert.ok(csv.includes('"Campo com, virgula"'));
});

test("CSV escapa campos com aspas duplas", () => {
  const result = makeResult();
  result.findings[0].title = 'Campo com "aspas"';
  const csv = buildAuditableReportCsv(result, "NFSE", FIXED_DATE);
  assert.ok(csv.includes('"Campo com ""aspas"""'));
});

// ── HTML/PDF tests ─────────────────────────────────────────────

test("HTML contém titulo e metadados do job", () => {
  const html = buildAuditableReportHtml(makeResult(), "NFSE", FIXED_DATE);
  assert.ok(html.includes("Tribultz - Relatorio Auditavel"));
  assert.ok(html.includes("job_xml_abc123"));
  assert.ok(html.includes("tenant-demo"));
  assert.ok(html.includes("LC 214"));
  assert.ok(html.includes("CBS 0,90%"));
  assert.ok(html.includes("IBS 0,10%"));
});

test("HTML contém tabela de findings com severidade", () => {
  const html = buildAuditableReportHtml(makeResult(), "NFSE", FIXED_DATE);
  assert.ok(html.includes("FATAL"));
  assert.ok(html.includes("ALERT"));
  assert.ok(html.includes("CST_3_DIGITS"));
  assert.ok(html.includes("NCM_PLACEHOLDER"));
});

test("HTML contém tabela de evidencias", () => {
  const html = buildAuditableReportHtml(makeResult(), "NFSE", FIXED_DATE);
  assert.ok(html.includes("E_XML_CST_LEN"));
  assert.ok(html.includes("E_XML_NCM_INFO"));
  assert.ok(html.includes("Trecho XML"));
});

test("HTML escapa caracteres especiais no snippet", () => {
  const result = makeResult();
  result.evidences[0].snippet = '<CST value="12" & test>';
  const html = buildAuditableReportHtml(result, "NFSE", FIXED_DATE);
  assert.ok(html.includes("&lt;CST value=&quot;12&quot; &amp; test&gt;"));
});

test("HTML gera documento valido com DOCTYPE", () => {
  const html = buildAuditableReportHtml(makeResult(), "NFSE", FIXED_DATE);
  assert.ok(html.startsWith("<!DOCTYPE html>"));
  assert.ok(html.includes("<html lang=\"pt-BR\">"));
  assert.ok(html.includes("</html>"));
});

test("CSV e HTML determinísticos para mesmo input", () => {
  const result = makeResult();
  const csv1 = buildAuditableReportCsv(result, "NFSE", FIXED_DATE);
  const csv2 = buildAuditableReportCsv(result, "NFSE", FIXED_DATE);
  const html1 = buildAuditableReportHtml(result, "NFSE", FIXED_DATE);
  const html2 = buildAuditableReportHtml(result, "NFSE", FIXED_DATE);
  assert.equal(csv1, csv2);
  assert.equal(html1, html2);
});
