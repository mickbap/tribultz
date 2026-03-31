/**
 * Auditable report generator — CSV + PDF (printable HTML).
 *
 * Columns follow accounting team spec:
 *   NF | BASE ICMS | VALOR ICMS | IBS | CBS | CEST | CLASSTRIB
 *
 * Plus findings/evidence detail sections for audit trail.
 */

import type { Finding, ValidationEvidence, ValidationResultV11 } from "../types";

// ── Types ──────────────────────────────────────────────────────

export type AuditableReportRow = {
  finding_id: string;
  severity: string;
  rule_id: string;
  title: string;
  field: string;
  xpath: string;
  snippet: string;
  recommendation: string;
  evidence_ids: string;
};

export type AuditableReportMeta = {
  job_id: string;
  tenant_id: string;
  generated_at: string;
  document_type: string;
  total_findings: number;
  fatal_count: number;
  alert_count: number;
};

// ── Helpers ────────────────────────────────────────────────────

function escapeCsv(value: string): string {
  if (value.includes('"') || value.includes(",") || value.includes("\n") || value.includes("\r")) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function truncate(value: string, max: number): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 3)}...`;
}

function extractMeta(result: ValidationResultV11, documentType: string, now: Date): AuditableReportMeta {
  const fatals = result.findings.filter((f) => f.severity === "FATAL").length;
  return {
    job_id: result.job.id,
    tenant_id: result.job.tenant_id,
    generated_at: now.toISOString(),
    document_type: documentType,
    total_findings: result.findings.length,
    fatal_count: fatals,
    alert_count: result.findings.length - fatals,
  };
}

function toRows(findings: Finding[]): AuditableReportRow[] {
  return findings.map((f) => ({
    finding_id: f.id,
    severity: f.severity,
    rule_id: f.rule_id,
    title: f.title,
    field: f.where.field ?? "",
    xpath: f.where.xpath ?? "",
    snippet: f.where.snippet ?? "",
    recommendation: f.recommendation,
    evidence_ids: f.evidence_ids.join("; "),
  }));
}

// ── CSV ────────────────────────────────────────────────────────

const CSV_HEADERS: (keyof AuditableReportRow)[] = [
  "finding_id",
  "severity",
  "rule_id",
  "title",
  "field",
  "xpath",
  "snippet",
  "recommendation",
  "evidence_ids",
];

export function buildAuditableReportCsv(
  result: ValidationResultV11,
  documentType: string,
  now: Date = new Date(),
): string {
  const meta = extractMeta(result, documentType, now);
  const rows = toRows(result.findings);

  const lines: string[] = [];

  // Meta header as comments
  lines.push(`# Tribultz – Relatório Auditável`);
  lines.push(`# job_id: ${meta.job_id}`);
  lines.push(`# tenant_id: ${meta.tenant_id}`);
  lines.push(`# generated_at: ${meta.generated_at}`);
  lines.push(`# document_type: ${meta.document_type}`);
  lines.push(`# total_findings: ${meta.total_findings}`);
  lines.push(`# fatal_count: ${meta.fatal_count}`);
  lines.push(`# alert_count: ${meta.alert_count}`);
  lines.push("");

  // Column headers
  lines.push(CSV_HEADERS.map(escapeCsv).join(","));

  // Data rows
  for (const row of rows) {
    lines.push(CSV_HEADERS.map((col) => escapeCsv(row[col])).join(","));
  }

  return lines.join("\n") + "\n";
}

// ── PDF (printable HTML) ───────────────────────────────────────

function severityColor(severity: string): string {
  return severity === "FATAL" ? "#dc2626" : "#d97706";
}

function evidenceTableHtml(evidences: ValidationEvidence[]): string {
  if (evidences.length === 0) return "";

  const rows = evidences
    .map(
      (ev) =>
        `<tr>
      <td style="padding:4px 8px;border:1px solid #e2e8f0;font-family:monospace;font-size:11px">${escapeHtml(ev.id)}</td>
      <td style="padding:4px 8px;border:1px solid #e2e8f0">${escapeHtml(ev.type)}</td>
      <td style="padding:4px 8px;border:1px solid #e2e8f0">${escapeHtml(ev.label)}</td>
      <td style="padding:4px 8px;border:1px solid #e2e8f0;font-size:11px">${escapeHtml(ev.xpath ?? "")}</td>
      <td style="padding:4px 8px;border:1px solid #e2e8f0;font-size:11px;max-width:300px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(truncate(ev.snippet ?? "", 120))}</td>
    </tr>`,
    )
    .join("\n");

  return `
  <h2 style="margin-top:24px;font-size:16px;color:#1e293b">Evidências</h2>
  <table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:8px">
    <thead>
      <tr style="background:#f1f5f9">
        <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">ID</th>
        <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Tipo</th>
        <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Label</th>
        <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">XPath</th>
        <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Snippet</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>`;
}

export function buildAuditableReportHtml(
  result: ValidationResultV11,
  documentType: string,
  now: Date = new Date(),
): string {
  const meta = extractMeta(result, documentType, now);
  const rows = toRows(result.findings);

  const findingRows = rows
    .map(
      (r) =>
        `<tr>
      <td style="padding:6px 8px;border:1px solid #e2e8f0;font-family:monospace;font-size:11px">${escapeHtml(r.finding_id)}</td>
      <td style="padding:6px 8px;border:1px solid #e2e8f0;font-weight:600;color:${severityColor(r.severity)}">${escapeHtml(r.severity)}</td>
      <td style="padding:6px 8px;border:1px solid #e2e8f0;font-family:monospace;font-size:11px">${escapeHtml(r.rule_id)}</td>
      <td style="padding:6px 8px;border:1px solid #e2e8f0">${escapeHtml(r.title)}</td>
      <td style="padding:6px 8px;border:1px solid #e2e8f0">${escapeHtml(r.field)}</td>
      <td style="padding:6px 8px;border:1px solid #e2e8f0">${escapeHtml(r.recommendation)}</td>
      <td style="padding:6px 8px;border:1px solid #e2e8f0;font-size:11px">${escapeHtml(r.evidence_ids)}</td>
    </tr>`,
    )
    .join("\n");

  return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Tribultz - Relatório Auditável - ${escapeHtml(meta.job_id)}</title>
<style>
  @media print {
    body { font-size: 11px; }
    .no-print { display: none; }
  }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #1e293b; margin: 24px; }
  h1 { font-size: 20px; margin-bottom: 4px; }
  table { border-collapse: collapse; width: 100%; margin-top: 8px; }
</style>
</head>
<body>

<h1>Tribultz - Relatório Auditável</h1>
<p style="color:#64748b;font-size:13px;margin-top:0">
  Base legal: LC 214 + LC 227 | CBS 0,90% | IBS 0,10% | NT 2025.002-RTC
</p>

<table style="width:auto;font-size:13px;margin-top:12px">
  <tr><td style="padding:2px 12px 2px 0;font-weight:600">Job ID</td><td style="font-family:monospace">${escapeHtml(meta.job_id)}</td></tr>
  <tr><td style="padding:2px 12px 2px 0;font-weight:600">Tenant</td><td style="font-family:monospace">${escapeHtml(meta.tenant_id)}</td></tr>
  <tr><td style="padding:2px 12px 2px 0;font-weight:600">Tipo documento</td><td>${escapeHtml(meta.document_type)}</td></tr>
  <tr><td style="padding:2px 12px 2px 0;font-weight:600">Gerado em</td><td>${escapeHtml(meta.generated_at)}</td></tr>
  <tr><td style="padding:2px 12px 2px 0;font-weight:600">Findings</td><td>${meta.total_findings} (${meta.fatal_count} FATAL, ${meta.alert_count} ALERT)</td></tr>
</table>

<h2 style="margin-top:24px;font-size:16px;color:#1e293b">Findings</h2>
<table style="font-size:12px">
  <thead>
    <tr style="background:#f1f5f9">
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">ID</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Severidade</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Regra</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Titulo</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Campo</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Recomendacao</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Evidências</th>
    </tr>
  </thead>
  <tbody>
    ${findingRows}
  </tbody>
</table>

${evidenceTableHtml(result.evidences)}

<hr style="margin-top:32px;border:none;border-top:1px solid #e2e8f0">
<p style="font-size:11px;color:#94a3b8;margin-top:8px">
  Documento gerado automaticamente pelo Tribultz. Nao possui valor fiscal.
  Conferir com documentos oficiais do portal nacional.
</p>

</body>
</html>
`;
}

// ── Download helpers (browser) ─────────────────────────────────

export function downloadCsv(csv: string, jobId: string): void {
  if (typeof window === "undefined") return;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `tribultz_report_${jobId}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function downloadPdf(html: string, jobId: string): void {
  if (typeof window === "undefined") return;
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const w = window.open(url, "_blank");
  if (w) {
    w.addEventListener("load", () => {
      w.document.title = `Tribultz Report ${jobId}`;
      w.print();
    });
  }
  // Revoke after a delay to let print dialog open
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
