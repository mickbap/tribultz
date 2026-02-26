import { AuditLog, Job } from "../types";

export type JobEvidenceArtifact = {
  filename: string;
  mimeType: string;
  content: string;
};

export type JobEvidenceBundle = {
  artifacts: JobEvidenceArtifact[];
  summaryMarkdown: string;
};

function toJson(data: unknown): string {
  return JSON.stringify(data, null, 2);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function maybeString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function extractXmlContent(job: Job): string | null {
  const inputXml = maybeString(job.input.xml);
  if (inputXml) return inputXml;

  const inputPayloadXml = maybeString(asRecord(job.input.payload)?.xml);
  if (inputPayloadXml) return inputPayloadXml;

  const outputXml = maybeString(asRecord(job.output)?.xml);
  if (outputXml) return outputXml;

  const outputPayloadXml = maybeString(asRecord(asRecord(job.output)?.payload)?.xml);
  if (outputPayloadXml) return outputPayloadXml;

  return null;
}

export function buildJobEvidenceBundle(job: Job, audits: AuditLog[], generatedAt: Date = new Date()): JobEvidenceBundle {
  const findings = job.findings ?? [];
  const evidences = job.evidence ?? [];
  const xmlContent = extractXmlContent(job);
  const nowIso = generatedAt.toISOString();

  const summaryLines = [
    "# Job Evidence Bundle",
    "",
    `- generated_at: ${nowIso}`,
    `- job_id: ${job.id}`,
    `- tenant_id: ${job.tenantId}`,
    `- status: ${job.status}`,
    `- findings_total: ${findings.length}`,
    `- evidences_total: ${evidences.length}`,
    `- audits_total: ${audits.length}`,
    `- xml_included: ${xmlContent ? "yes" : "no"}`,
    "",
    "## Files",
    "- job.json",
    "- audit.json",
    "- findings.json",
    "- evidences.json",
    "- summary.md",
    ...(xmlContent ? ["- xml.xml"] : ["- xml.xml (not available in payload)"]),
  ];
  const summaryMarkdown = `${summaryLines.join("\n")}\n`;

  const artifacts: JobEvidenceArtifact[] = [
    { filename: "job.json", mimeType: "application/json", content: toJson(job) },
    { filename: "audit.json", mimeType: "application/json", content: toJson(audits) },
    { filename: "findings.json", mimeType: "application/json", content: toJson(findings) },
    { filename: "evidences.json", mimeType: "application/json", content: toJson(evidences) },
    { filename: "summary.md", mimeType: "text/markdown", content: summaryMarkdown },
  ];

  if (xmlContent) {
    artifacts.push({ filename: "xml.xml", mimeType: "application/xml", content: xmlContent });
  }

  return { artifacts, summaryMarkdown };
}

export function downloadJobEvidenceBundle(bundle: JobEvidenceBundle, jobId: string): void {
  if (typeof window === "undefined") return;
  for (const artifact of bundle.artifacts) {
    const blob = new Blob([artifact.content], { type: `${artifact.mimeType};charset=utf-8` });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${jobId}-${artifact.filename}`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }
}
