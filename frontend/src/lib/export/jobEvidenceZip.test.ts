import assert from "node:assert/strict";
import test from "node:test";
import { unzipSync, strFromU8 } from "fflate";

import { buildJobEvidenceBundle } from "./jobEvidenceBundle";
import { buildJobEvidenceZip, makeJobEvidenceZipFilename } from "./jobEvidenceZip";
import type { AuditLog, Job } from "../types";

function makeJob(xml?: string): Job {
  return {
    id: "job:tenant-a/0001",
    tenantId: "tenant-a",
    jobType: "xml_validation",
    status: "SUCCESS",
    createdAt: "2026-02-26T12:00:00.000Z",
    updatedAt: "2026-02-26T12:00:02.000Z",
    input: xml ? { document_type: "NFSE", xml } : { document_type: "NFSE" },
    output: { status: "PASS" },
    evidence: [{ type: "job", job_id: "job:tenant-a/0001", href: "/jobs/job:tenant-a/0001", label: "Job" }],
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
    id: "audit-job-1",
    tenantId: "tenant-a",
    jobId: "job:tenant-a/0001",
    action: "validation_succeeded",
    createdAt: "2026-02-26T12:00:03.000Z",
    payload: { status: "SUCCESS" },
  },
];

test("makeJobEvidenceZipFilename sanitiza jobId e inclui timestamp", () => {
  const name = makeJobEvidenceZipFilename("job:1", new Date("2026-02-26T17:02:39.123Z"));
  assert.equal(name, "job_1_20260226T170239Z.zip");
});

test("ZIP inclui arquivos base e xml.xml quando XML existe", () => {
  const bundle = buildJobEvidenceBundle(makeJob("<root />"), audits, new Date("2026-02-26T16:00:00.000Z"));
  const zipBytes = buildJobEvidenceZip(bundle);

  const files = unzipSync(zipBytes);

  for (const required of ["job.json", "audit.json", "findings.json", "evidences.json", "summary.md", "xml.xml"]) {
    assert.ok(files[required], `missing ${required}`);
  }

  const jobJson = JSON.parse(strFromU8(files["job.json"]));
  assert.equal(jobJson.id, "job:tenant-a/0001");

  const summary = strFromU8(files["summary.md"]);
  assert.match(summary, /xml_included: yes/);
});

test("ZIP nao inclui xml.xml quando XML nao existe no bundle", () => {
  const bundle = buildJobEvidenceBundle(makeJob(), audits, new Date("2026-02-26T16:00:00.000Z"));
  const zipBytes = buildJobEvidenceZip(bundle);

  const files = unzipSync(zipBytes);
  assert.ok(files["job.json"]);
  assert.ok(files["summary.md"]);
  assert.equal(files["xml.xml"], undefined);

  const summary = strFromU8(files["summary.md"]);
  assert.match(summary, /xml_included: no/);
});
