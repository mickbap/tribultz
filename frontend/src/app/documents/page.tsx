"use client";

import { useEffect, useMemo, useState } from "react";
import { listDocuments, getDocumentDownloadUrl, type DocumentResponse } from "@/lib/api";

export default function DocumentsPage(): JSX.Element {
  const [docs, setDocs] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [onlyCorrected, setOnlyCorrected] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load(): Promise<void> {
      setLoading(true);
      const rows = await listDocuments({ limit: 100 });
      if (!cancelled) setDocs(rows);
      setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    if (!onlyCorrected) return docs;
    return docs.filter((d) => (d.fiscal_metadata?.["artifact_kind"] as string) === "corrected_xml");
  }, [docs, onlyCorrected]);

  async function download(doc: DocumentResponse): Promise<void> {
    const { download_url } = await getDocumentDownloadUrl(doc.id);
    window.open(download_url, "_blank", "noopener,noreferrer");
  }

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Documentos</h1>
        <p className="text-sm text-slate-500">Arquivos do tenant (originais, corrigidos e outros artefatos).</p>
      </header>

      <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={onlyCorrected} onChange={(e) => setOnlyCorrected(e.target.checked)} />
          Somente XML corrigido
        </label>
        <span className="text-slate-400">|</span>
        <span className="text-slate-600">{filtered.length} documento(s)</span>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        {loading ? (
          <div className="p-4 text-sm text-slate-500">Carregando…</div>
        ) : filtered.length === 0 ? (
          <div className="p-4 text-sm text-slate-500">Nenhum documento encontrado.</div>
        ) : (
          <ul className="divide-y divide-slate-200">
            {filtered.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between p-3 text-sm">
                <div className="min-w-0">
                  <p className="truncate font-medium text-slate-800">
                    {doc.original_filename ?? doc.storage_key.split("/").pop()}
                  </p>
                  <p className="text-xs text-slate-500">
                    {doc.doc_type} • {doc.content_type ?? ""} • {new Date(doc.created_at).toLocaleString()}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void download(doc)}
                  className="ml-3 shrink-0 rounded border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                >
                  Baixar
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
