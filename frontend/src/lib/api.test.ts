import test from "node:test";
import assert from "node:assert/strict";
import { adaptValidationResult } from "./api";

// Backend /api/v1/validate/xml retorna shape flat (job_id, audit_id).
// Frontend consome ValidationResultV11 (job.{id,...}, audit.{id,...}).
// adaptValidationResult faz a transformação — sem ela a página crasha
// em result.job.id (issue: Application error após submit de XML em Trial).

test("adapter: flat backend payload → nested ValidationResultV11", () => {
  const raw = {
    job_id: "job-abc",
    audit_id: "aud-xyz",
    document_type: "NFSE",
    findings: [],
    evidences: [],
    fatals: 0,
    alerts: 0,
    created_at: "2026-04-19T16:00:00Z",
  };
  const out = adaptValidationResult(raw, "tenant-1", "txn-1");

  assert.equal(out.job.id, "job-abc");
  assert.equal(out.job.created_at, "2026-04-19T16:00:00Z");
  assert.equal(out.job.tenant_id, "tenant-1");
  assert.equal(out.job.transaction_id, "txn-1");
  assert.equal(out.audit.id, "aud-xyz");
  assert.equal(out.audit.job_id, "job-abc");
  assert.deepEqual(out.audit.events, []);
  assert.equal(out.transaction_id, "txn-1");
});

test("adapter: preserva findings e evidences", () => {
  const findings = [
    { id: "f1", rule_id: "CBS_RATE", severity: "ERROR" as const, title: "t", description: "d", evidence_ids: [] },
  ];
  const evidences = [{ id: "e1", type: "xml" as const, label: "Evidência" }];
  const raw = {
    job_id: "j",
    audit_id: "a",
    document_type: "NFE",
    findings,
    evidences,
    fatals: 1,
    alerts: 0,
    created_at: "2026-01-01T00:00:00Z",
  };
  const out = adaptValidationResult(raw, "t", "x");
  assert.equal(out.findings.length, 1);
  assert.equal(out.findings[0].rule_id, "CBS_RATE");
  assert.equal(out.evidences.length, 1);
  assert.equal(out.evidences[0].id, "e1");
});

test("adapter: payload já aninhado passa através (forward-compat)", () => {
  const raw = {
    job: { id: "j2", created_at: "2026-02-02T00:00:00Z", tenant_id: "t9", transaction_id: "tx9" },
    audit: { id: "a2", job_id: "j2", events: [] },
    findings: [],
    evidences: [],
    transaction_id: "tx9",
  };
  const out = adaptValidationResult(raw, "t-default", "txn-default");
  assert.equal(out.job.id, "j2");
  assert.equal(out.job.tenant_id, "t9");
  assert.equal(out.audit.id, "a2");
  assert.equal(out.transaction_id, "tx9");
});

test("adapter: campos ausentes não quebram — defaults seguros", () => {
  const out = adaptValidationResult({}, "tenant-z", "txn-z");
  assert.equal(out.job.id, "");
  assert.equal(out.job.tenant_id, "tenant-z");
  assert.equal(out.job.transaction_id, "txn-z");
  assert.equal(out.audit.id, "");
  assert.equal(out.audit.job_id, "");
  assert.deepEqual(out.audit.events, []);
  assert.deepEqual(out.findings, []);
  assert.deepEqual(out.evidences, []);
});
