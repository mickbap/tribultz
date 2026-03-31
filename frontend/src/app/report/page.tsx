"use client";

import Link from "next/link";

export default function ReportPage() {
  return (
    <section className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Relatório Auditável</h1>
        <p className="text-sm text-slate-500">
          Exporte relatórios CSV e PDF após validar um documento XML.
        </p>
      </header>

      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
        <p className="text-sm text-slate-600">
          Para gerar um relatório auditável, valide um XML na página de validação.
          Os botões CSV e PDF aparecem após a validação.
        </p>
        <Link
          href="/validate-xml"
          className="mt-3 inline-block rounded-lg bg-tribultz-600 px-4 py-2 text-sm font-semibold text-white hover:bg-tribultz-700"
        >
          Ir para Validar XML
        </Link>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
        <h2 className="mb-2 font-semibold text-slate-900">Formato do relatório</h2>
        <ul className="list-inside list-disc space-y-1">
          <li><strong>CSV</strong> — Findings com colunas: ID, Severidade, Regra, Título, Campo, XPath, Snippet, Recomendação, Evidências</li>
          <li><strong>PDF</strong> — Documento formatado com tabela de findings, evidências e metadados do job (via impressão do navegador)</li>
        </ul>
        <p className="mt-3 text-xs text-slate-500">
          Base legal: LC 214 + LC 227 | CBS 0,10% | IBS 0,90%
        </p>
      </div>
    </section>
  );
}
