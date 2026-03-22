import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { buildBatchReportCsv, buildBatchReportHtml, type BatchEntry } from "./batchReport";

function makeFinding(id: string, severity: "FATAL" | "ALERT", ruleId: string) {
  return {
    id,
    severity,
    rule_id: ruleId,
    title: `Finding ${id}`,
    where: { field: "tag", xpath: "/root/tag" },
    recommendation: "Fix it",
    evidence_ids: [`ev-${id}`],
  };
}

function makeResult(jobId: string, findings: ReturnType<typeof makeFinding>[]) {
  return {
    job: { id: jobId, created_at: "2026-03-22T00:00:00Z", tenant_id: "tenant-a" },
    audit: { id: `aud-${jobId}`, job_id: jobId, events: [] },
    findings,
    evidences: [],
  };
}

const FIXED_DATE = new Date("2026-03-22T12:00:00Z");

const entries: BatchEntry[] = [
  {
    filename: "nota1.xml",
    result: makeResult("job-1", [makeFinding("f1", "FATAL", "R01")]),
  },
  {
    filename: "nota2.xml",
    result: makeResult("job-2", [makeFinding("f2", "ALERT", "R05")]),
  },
  {
    filename: "nota3.xml",
    result: makeResult("job-3", []),
  },
];

describe("batchReport CSV", () => {
  it("should include meta header comments", () => {
    const csv = buildBatchReportCsv(entries, "NFSE", FIXED_DATE);
    assert.ok(csv.includes("# Tribultz"));
    assert.ok(csv.includes("# total_files: 3"));
    assert.ok(csv.includes("# pass: 2"));
    assert.ok(csv.includes("# fail: 1"));
  });

  it("should include summary rows for each file", () => {
    const csv = buildBatchReportCsv(entries, "NFSE", FIXED_DATE);
    assert.ok(csv.includes("nota1.xml"));
    assert.ok(csv.includes("nota2.xml"));
    assert.ok(csv.includes("nota3.xml"));
    assert.ok(csv.includes("FAIL"));
    assert.ok(csv.includes("PASS"));
  });

  it("should include finding detail rows", () => {
    const csv = buildBatchReportCsv(entries, "NFSE", FIXED_DATE);
    assert.ok(csv.includes("# Detalhes dos Findings"));
    assert.ok(csv.includes("f1"));
    assert.ok(csv.includes("R01"));
    assert.ok(csv.includes("f2"));
  });

  it("should be deterministic", () => {
    const a = buildBatchReportCsv(entries, "NFSE", FIXED_DATE);
    const b = buildBatchReportCsv(entries, "NFSE", FIXED_DATE);
    assert.equal(a, b);
  });
});

describe("batchReport HTML", () => {
  it("should include doctype and lang", () => {
    const html = buildBatchReportHtml(entries, "NFSE", FIXED_DATE);
    assert.ok(html.startsWith("<!DOCTYPE html>"));
    assert.ok(html.includes('lang="pt-BR"'));
  });

  it("should show summary stats", () => {
    const html = buildBatchReportHtml(entries, "NFSE", FIXED_DATE);
    assert.ok(html.includes("2 PASS"));
    assert.ok(html.includes("1 FAIL"));
  });

  it("should show per-file rows", () => {
    const html = buildBatchReportHtml(entries, "NFSE", FIXED_DATE);
    assert.ok(html.includes("nota1.xml"));
    assert.ok(html.includes("nota2.xml"));
    assert.ok(html.includes("nota3.xml"));
  });

  it("should include legal base reference", () => {
    const html = buildBatchReportHtml(entries, "NFSE", FIXED_DATE);
    assert.ok(html.includes("LC 214"));
    assert.ok(html.includes("LC 227"));
  });

  it("should be deterministic", () => {
    const a = buildBatchReportHtml(entries, "NFSE", FIXED_DATE);
    const b = buildBatchReportHtml(entries, "NFSE", FIXED_DATE);
    assert.equal(a, b);
  });
});
