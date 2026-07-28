"use client";

import { useRef, useState } from "react";
import { useAdminData, adminUpload } from "@/lib/useAdminData";

type InvoiceResult = {
  label: string;
  status: "PASS" | "FAIL";
  fatal_count: number;
};

type DiagnosticResponse = {
  id: string;
  office_name: string;
  invoice_count: number;
  rejected_count: number;
  download_url: string;
  trial_url: string;
  invoices: InvoiceResult[];
};

type DiagnosticListItem = {
  id: string;
  office_name: string;
  invoice_count: number;
  rejected_count: number;
  created_at: string;
};
type ListResp = { total: number; items: DiagnosticListItem[] };

export default function AdminProspeccaoPage() {
  const { data, reload } = useAdminData<ListResp>("/api/v1/admin/prospect-diagnostics?limit=50");
  const [officeName, setOfficeName] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DiagnosticResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!officeName.trim() || files.length === 0) {
      setError("Informe o nome do escritório e ao menos um XML.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const form = new FormData();
      form.append("office_name", officeName.trim());
      files.forEach((f) => form.append("files", f));
      const resp = await adminUpload<DiagnosticResponse>("/api/v1/admin/prospect-diagnostics", form);
      setResult(resp);
      setOfficeName("");
      setFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao gerar diagnóstico.");
    } finally {
      setBusy(false);
    }
  }

  function copyTrialUrl(url: string) {
    navigator.clipboard.writeText(url).catch(() => {});
  }

  const inputCls = "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm";

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-900">Prospecção — Diagnóstico Gratuito</h1>
      <p className="mb-5 text-sm text-slate-500">
        Sobe de 10 a 20 XMLs de um escritório contábil prospect e gera um PDF auditável com o
        que seria rejeitado hoje, a base legal e um link de trial atribuído — sem que o prospect
        precise ter conta.
      </p>

      <form onSubmit={submit} className="mb-8 grid grid-cols-1 gap-3 rounded-xl border border-slate-200 p-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">Nome do escritório *</label>
          <input
            className={inputCls}
            value={officeName}
            required
            placeholder="Contabilidade Exemplo Ltda."
            onChange={(e) => setOfficeName(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">
            XMLs (10 a 20 notas) *
          </label>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xml"
            multiple
            className={inputCls}
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          />
          {files.length > 0 && (
            <p className="mt-1 text-xs text-slate-500">{files.length} arquivo(s) selecionado(s).</p>
          )}
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div>
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-[#2956E3] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Gerando diagnóstico…" : "Gerar diagnóstico"}
          </button>
        </div>
      </form>

      {result && (
        <div className="mb-8 rounded-xl border border-green-200 bg-green-50 p-4">
          <h2 className="mb-2 text-sm font-semibold text-green-800">
            Diagnóstico gerado para {result.office_name}
          </h2>
          <p className="mb-3 text-sm text-green-700">
            {result.rejected_count} de {result.invoice_count} nota(s) seriam rejeitadas hoje.
          </p>
          <div className="mb-3 flex flex-wrap gap-2">
            <a
              href={result.download_url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg bg-[#2956E3] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
            >
              Baixar PDF
            </a>
            <button
              type="button"
              onClick={() => copyTrialUrl(result.trial_url)}
              className="rounded-lg border border-green-300 bg-white px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100"
            >
              Copiar link de trial atribuído
            </button>
          </div>
          <div className="overflow-x-auto rounded-lg border border-green-200 bg-white">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-50 text-left uppercase tracking-wide text-slate-400">
                  <th className="px-3 py-2">Arquivo</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Erros críticos</th>
                </tr>
              </thead>
              <tbody>
                {result.invoices.map((inv, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-3 py-2 font-mono">{inv.label}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          inv.status === "PASS" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                        }`}
                      >
                        {inv.status === "PASS" ? "Conforme" : "Seria rejeitada"}
                      </span>
                    </td>
                    <td className="px-3 py-2">{inv.fatal_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <h2 className="mb-3 text-sm font-semibold text-slate-700">Diagnósticos anteriores</h2>
      {data && (
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Escritório</th>
                <th className="px-4 py-3">Notas</th>
                <th className="px-4 py-3">Rejeitadas</th>
                <th className="px-4 py-3">Gerado em</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{d.office_name}</td>
                  <td className="px-4 py-3">{d.invoice_count}</td>
                  <td className="px-4 py-3">{d.rejected_count}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {new Date(d.created_at).toLocaleDateString("pt-BR")}
                  </td>
                </tr>
              ))}
              {data.items.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-slate-400">
                    Nenhum diagnóstico gerado ainda.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
