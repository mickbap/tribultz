import assert from "node:assert/strict";
import test from "node:test";
import { createClosingSnapshot } from "./aggregate";
import { AuditLog, ExceptionRequest, Job } from "../types";

const NOW = new Date("2026-02-26T16:00:00.000Z");

function makeJob(id: string, createdAt: string, fatalCount: number): Job {
  return {
    id,
    tenantId: "tenant-a",
    jobType: "xml_validation",
    status: "SUCCESS",
    createdAt,
    updatedAt: createdAt,
    input: {},
    output: {},
    evidence: [],
    findings: Array.from({ length: fatalCount }, (_, i) => ({
      id: `f-${id}-${i + 1}`,
      severity: "FATAL",
      rule_id: "RULE_X",
      title: "Fatal",
      where: {},
      recommendation: "Fix",
      evidence_ids: [],
    })),
  };
}

function makeAudit(id: string, createdAt: string): AuditLog {
  return {
    id,
    tenantId: "tenant-a",
    action: "validation_succeeded",
    createdAt,
    payload: {},
  };
}

function makeException(id: string, createdAt: string, status: ExceptionRequest["status"]): ExceptionRequest {
  return {
    id,
    tenant_id: "tenant-a",
    job_id: "job-a",
    finding_id: "finding-1",
    rule_id: "RULE_X",
    justification: "Need exception",
    status,
    created_by: "operator.demo",
    created_at: createdAt,
  };
}

test("createClosingSnapshot calcula metricas da janela de 7 dias", () => {
  const jobs = [
    makeJob("job-1", "2026-02-26T10:00:00.000Z", 2),
    makeJob("job-2", "2026-02-22T10:00:00.000Z", 1),
    makeJob("job-old", "2026-02-10T10:00:00.000Z", 5),
  ];
  const audits = [
    makeAudit("audit-1", "2026-02-25T10:00:00.000Z"),
    makeAudit("audit-old", "2026-02-01T10:00:00.000Z"),
  ];
  const exceptions = [
    makeException("exc-open", "2026-02-24T10:00:00.000Z", "OPEN"),
    makeException("exc-approved", "2026-02-24T12:00:00.000Z", "APPROVED"),
    makeException("exc-old-open", "2026-01-20T12:00:00.000Z", "OPEN"),
  ];

  const snapshot = createClosingSnapshot({ jobs, audits, exceptions, now: NOW });

  assert.equal(snapshot.counts.jobsExecuted, 2);
  assert.equal(snapshot.counts.fatalFindings, 3);
  assert.equal(snapshot.counts.recentAudits, 1);
  assert.equal(snapshot.counts.openExceptions, 1);
  assert.deepEqual(
    snapshot.recentJobs.map((row) => row.id),
    ["job-1", "job-2"],
  );
  assert.deepEqual(
    snapshot.openExceptionRows.map((row) => row.id),
    ["exc-open"],
  );
});
