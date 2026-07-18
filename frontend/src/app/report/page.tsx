"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { listReports, getReportDownloadUrl, ReportListItem } from "@/lib/api";
import { formatDateTimeBR } from "@/lib/formatDateTimeBR";

export default function ReportPage() {
  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    listReports({ limit: 50 }).then((data) => {
      setReports(data);
      setLoading(false);
    });
  }, []);

  async function handleDownload(reportId: string) {
    setDownloading(reportId);
    try {
      const { download_url } = await getReportDownloadUrl(reportId);
      window.open(download_url, "_blank");
    } catch (err) {
      console.error("Erro ao obter URL de download:", err);
    } finally {
      setDownloading(null);
    }
  }

  return (
    <section className="space-y-5">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Relatórios Auditáveis</h1>
          <p className="text-sm text-slate-500 mt-1">
            Histórico de relatórios PDF gerados — CBS/IBS · LC 214/2025
          </p>
        </div>
        <Link
          href="/validate-xml"
          className="rounded-lg bg-tribultz-600 px-4 py-2 text-sm font-semibold text-white hover:bg-tribultz-700 transition-colors"
        >
          Gerar novo
        </Link>
      </header>

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Job</th>
                <th className="px-4 py-3">Data</th>
                <th className="px-4 py-3">Tamanho</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Ação</th>
              </tr>
            </thead>
            <tbody>
              {[1, 2, 3].map((i) => (
                <tr key={i} className="border-t border-slate-100">
                  {[1, 2, 3, 4, 5, 6].map((j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-4 animate-pulse rounded bg-slate-200" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : reports.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
          <p className="text-sm text-slate-600">
            Nenhum relatório gerado. Valide um XML para começar.
          </p>
          <Link
            href="/validate-xml"
            className="mt-3 inline-block rounded-lg bg-tribultz-600 px-4 py-2 text-sm font-semibold text-white hover:bg-tribultz-700 transition-colors"
          >
            Ir para Validar XML
          </Link>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Job</th>
                <th className="px-4 py-3">Data</th>
                <th className="px-4 py-3">Tamanho</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Ação</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3">
                    {r.report_type === "validation" ? (
                      <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                        Validação
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-medium text-purple-700">
                        Lote
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {r.job_id ? r.job_id.slice(0, 8) + "…" : "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {formatDateTimeBR(r.created_at)}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {r.file_size != null ? (r.file_size / 1024).toFixed(1) + " KB" : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {r.status === "ready" ? (
                      <span className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
                        Pronto
                      </span>
                    ) : r.status === "generating" ? (
                      <span className="inline-flex animate-pulse items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                        Gerando
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">
                        Erro
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleDownload(r.id)}
                      disabled={r.status !== "ready" || downloading === r.id}
                      className="rounded-lg bg-tribultz-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-tribultz-700 disabled:cursor-not-allowed disabled:opacity-40 transition-colors"
                    >
                      {downloading === r.id ? "…" : "⬇ Baixar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
