/**
 * Batch report generator — CSV + PDF (printable HTML).
 *
 * Consolidates multiple validation results into a single report
 * with per-file PASS/FAIL status and aggregate findings.
 */

import type { Finding, ValidationEvidence, ValidationResultV11 } from "../types";

export type BatchEntry = {
  filename: string;
  result: ValidationResultV11;
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

function fatalCount(result: ValidationResultV11): number {
  return result.findings.filter((f) => f.severity === "FATAL").length;
}

function passOrFail(result: ValidationResultV11): string {
  return fatalCount(result) > 0 ? "FAIL" : "PASS";
}

// ── CSV ────────────────────────────────────────────────────────

export function buildBatchReportCsv(
  entries: BatchEntry[],
  documentType: string,
  now: Date = new Date(),
): string {
  const lines: string[] = [];
  const pass = entries.filter((e) => passOrFail(e.result) === "PASS").length;
  const fail = entries.length - pass;
  const totalFindings = entries.reduce((s, e) => s + e.result.findings.length, 0);

  lines.push(`# Tribultz – Relatório de Lote`);
  lines.push(`# generated_at: ${now.toISOString()}`);
  lines.push(`# document_type: ${documentType}`);
  lines.push(`# total_files: ${entries.length}`);
  lines.push(`# pass: ${pass}`);
  lines.push(`# fail: ${fail}`);
  lines.push(`# total_findings: ${totalFindings}`);
  lines.push("");

  // Summary table
  lines.push("arquivo,job_id,resultado,findings,fatal,alert");
  for (const entry of entries) {
    const fatals = fatalCount(entry.result);
    const alerts = entry.result.findings.length - fatals;
    lines.push(
      [
        escapeCsv(entry.filename),
        escapeCsv(entry.result.job.id),
        passOrFail(entry.result),
        String(entry.result.findings.length),
        String(fatals),
        String(alerts),
      ].join(","),
    );
  }

  lines.push("");
  lines.push("# Detalhes dos Findings");
  lines.push("arquivo,finding_id,severity,rule_id,title,field,xpath,recommendation");

  for (const entry of entries) {
    for (const f of entry.result.findings) {
      lines.push(
        [
          escapeCsv(entry.filename),
          escapeCsv(f.id),
          escapeCsv(f.severity),
          escapeCsv(f.rule_id),
          escapeCsv(f.title),
          escapeCsv(f.where.field ?? ""),
          escapeCsv(f.where.xpath ?? ""),
          escapeCsv(f.recommendation),
        ].join(","),
      );
    }
  }

  return lines.join("\n") + "\n";
}

// ── PDF (printable HTML) ───────────────────────────────────────

export function buildBatchReportHtml(
  entries: BatchEntry[],
  documentType: string,
  now: Date = new Date(),
): string {
  const pass = entries.filter((e) => passOrFail(e.result) === "PASS").length;
  const fail = entries.length - pass;
  const totalFindings = entries.reduce((s, e) => s + e.result.findings.length, 0);

  const summaryRows = entries
    .map((entry) => {
      const fatals = fatalCount(entry.result);
      const alerts = entry.result.findings.length - fatals;
      const status = passOrFail(entry.result);
      const statusColor = status === "PASS" ? "#16a34a" : "#dc2626";
      return `<tr>
        <td style="padding:6px 8px;border:1px solid #e2e8f0">${escapeHtml(entry.filename)}</td>
        <td style="padding:6px 8px;border:1px solid #e2e8f0;font-family:monospace;font-size:11px">${escapeHtml(entry.result.job.id)}</td>
        <td style="padding:6px 8px;border:1px solid #e2e8f0;font-weight:700;color:${statusColor}">${status}</td>
        <td style="padding:6px 8px;border:1px solid #e2e8f0;text-align:center">${entry.result.findings.length}</td>
        <td style="padding:6px 8px;border:1px solid #e2e8f0;text-align:center;color:#dc2626">${fatals}</td>
        <td style="padding:6px 8px;border:1px solid #e2e8f0;text-align:center;color:#d97706">${alerts}</td>
      </tr>`;
    })
    .join("\n");

  const findingRows = entries
    .flatMap((entry) =>
      entry.result.findings.map(
        (f) =>
          `<tr>
        <td style="padding:4px 8px;border:1px solid #e2e8f0;font-size:11px">${escapeHtml(entry.filename)}</td>
        <td style="padding:4px 8px;border:1px solid #e2e8f0;font-weight:600;color:${f.severity === "FATAL" ? "#dc2626" : "#d97706"}">${escapeHtml(f.severity)}</td>
        <td style="padding:4px 8px;border:1px solid #e2e8f0;font-family:monospace;font-size:11px">${escapeHtml(f.rule_id)}</td>
        <td style="padding:4px 8px;border:1px solid #e2e8f0">${escapeHtml(f.title)}</td>
        <td style="padding:4px 8px;border:1px solid #e2e8f0">${escapeHtml(f.where.field ?? "")}</td>
        <td style="padding:4px 8px;border:1px solid #e2e8f0">${escapeHtml(f.recommendation)}</td>
      </tr>`,
      ),
    )
    .join("\n");

  return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Tribultz - Relatório de Lote</title>
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

<h1>Tribultz - Relatório de Lote</h1>
<p style="color:#64748b;font-size:13px;margin-top:0">
  Base legal: LC 214 + LC 227 | CBS 0,10% | IBS 0,90%
</p>

<table style="width:auto;font-size:13px;margin-top:12px">
  <tr><td style="padding:2px 12px 2px 0;font-weight:600">Gerado em</td><td>${escapeHtml(now.toISOString())}</td></tr>
  <tr><td style="padding:2px 12px 2px 0;font-weight:600">Tipo documento</td><td>${escapeHtml(documentType)}</td></tr>
  <tr><td style="padding:2px 12px 2px 0;font-weight:600">Total arquivos</td><td>${entries.length}</td></tr>
  <tr><td style="padding:2px 12px 2px 0;font-weight:600">PASS / FAIL</td><td style="color:#16a34a">${pass} PASS</td></tr>
  <tr><td></td><td style="color:#dc2626">${fail} FAIL</td></tr>
  <tr><td style="padding:2px 12px 2px 0;font-weight:600">Total findings</td><td>${totalFindings}</td></tr>
</table>

<h2 style="margin-top:24px;font-size:16px;color:#1e293b">Resumo por Arquivo</h2>
<table style="font-size:12px">
  <thead>
    <tr style="background:#f1f5f9">
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Arquivo</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Job ID</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Resultado</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:center">Findings</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:center">FATAL</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:center">ALERT</th>
    </tr>
  </thead>
  <tbody>
    ${summaryRows}
  </tbody>
</table>

<h2 style="margin-top:24px;font-size:16px;color:#1e293b">Findings Detalhados</h2>
<table style="font-size:12px">
  <thead>
    <tr style="background:#f1f5f9">
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Arquivo</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Severidade</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Regra</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Titulo</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Campo</th>
      <th style="padding:6px 8px;border:1px solid #e2e8f0;text-align:left">Recomendacao</th>
    </tr>
  </thead>
  <tbody>
    ${findingRows}
  </tbody>
</table>

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

export function downloadBatchCsv(csv: string, batchId: string): void {
  if (typeof window === "undefined") return;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `tribultz_batch_${batchId}_${Date.now()}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function downloadBatchPdf(html: string, batchId: string): void {
  if (typeof window === "undefined") return;
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const w = window.open(url, "_blank");
  if (w) {
    w.addEventListener("load", () => {
      w.document.title = `Tribultz Batch Report ${batchId}`;
      w.print();
    });
  }
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
