import { strToU8, zipSync } from "fflate";
import type { JobEvidenceBundle } from "./jobEvidenceBundle";

function sanitizeJobId(jobId: string): string {
  return jobId.replace(/[^a-zA-Z0-9._-]+/g, "_");
}

function formatZipTimestamp(date: Date): string {
  // 2026-02-26T17:02:39.123Z -> 20260226T170239Z
  return date
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\.\d{3}Z$/, "Z");
}

export function makeJobEvidenceZipFilename(jobId: string, generatedAt: Date = new Date()): string {
  const safeJobId = sanitizeJobId(jobId);
  const ts = formatZipTimestamp(generatedAt);
  return `${safeJobId}_${ts}.zip`;
}

export function buildJobEvidenceZip(bundle: JobEvidenceBundle): Uint8Array {
  // Keep order and file names from the bundle.
  const files: Record<string, Uint8Array> = {};
  for (const artifact of bundle.artifacts) {
    files[artifact.filename] = strToU8(artifact.content);
  }
  return zipSync(files, { level: 6 });
}

export function downloadZip(zipBytes: Uint8Array, filename: string): void {
  if (typeof window === "undefined") return;

  const arrayBuffer = new ArrayBuffer(zipBytes.byteLength);
  new Uint8Array(arrayBuffer).set(zipBytes);
  const blob = new Blob([arrayBuffer], { type: "application/zip" });
  const url = URL.createObjectURL(blob);

  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  URL.revokeObjectURL(url);
}
