import assert from "node:assert/strict";
import test from "node:test";
import { buildJobEvidenceBundle } from "./jobEvidenceBundle";
import { AuditLog, Job } from "../types";

function makeJob(xml?: string): Job {
  return {
    id: "job-tenant-a-0001",
    tenantId: "tenant-a",
    jobType: "xml_validation",
    status: "SUCCESS",
    createdAt: "2026-02-26T12:00:00.000Z",
    updatedAt: "2026-02-26T12:00:02.000Z",
    input: xml ? { document_type: "NFSE", xml } : { document_type: "NFSE" },
    output: { status: "PASS" },
    evidence: [{ type: "job", job_id: "job-tenant-a-0001", href: "/jobs/job-tenant-a-0001", label: "Job" }],
    findings: [
      {
        id: "F_1",
        severity: "FATAL",
        rule_id: "RULE_FATAL",
        title: "Campo invalido",
        where: { xpath: "/NFSe/Servico" },
        recommendation: "Corrigir campo",
        evidence_ids: ["E_1"],
      },
    ],
  };
}

const audits: AuditLog[] = [
  {
    id: "audit-job-tenant-a-0001",
    tenantId: "tenant-a",
    jobId: "job-tenant-a-0001",
    action: "validation_succeeded",
    createdAt: "2026-02-26T12:00:03.000Z",
    payload: { status: "SUCCESS" },
  },
];

test("buildJobEvidenceBundle inclui xml.xml quando XML existe", () => {
  const bundle = buildJobEvidenceBundle(makeJob("<root />"), audits, new Date("2026-02-26T16:00:00.000Z"));
  const files = bundle.artifacts.map((item) => item.filename);

  assert.deepEqual(files, ["job.json", "audit.json", "findings.json", "evidences.json", "summary.md", "xml.xml"]);
  assert.match(bundle.summaryMarkdown, /job_id: job-tenant-a-0001/);
  assert.match(bundle.summaryMarkdown, /xml_included: yes/);
});

test("buildJobEvidenceBundle nao inclui xml.xml quando XML nao existe", () => {
  const bundle = buildJobEvidenceBundle(makeJob(), audits, new Date("2026-02-26T16:00:00.000Z"));
  const files = bundle.artifacts.map((item) => item.filename);

  assert.deepEqual(files, ["job.json", "audit.json", "findings.json", "evidences.json", "summary.md"]);
  assert.match(bundle.summaryMarkdown, /xml_included: no/);
});
