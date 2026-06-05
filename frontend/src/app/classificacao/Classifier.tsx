"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/api";

const WA_NUMBER = "5551991881026";
const WA_REJEICAO = `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent(
  "Olá! Estou com Rejeição 1024 na NF-e (cClassTrib incorreto) e preciso de ajuda urgente.",
)}`;

type SuggestResult = {
  ncm: string;
  ncm_descricao: string;
  confidence: number;
  cClassTrib: string | null;
  aviso: string | null;
};

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const cls = value >= 0.85
    ? "bg-emerald-100 text-emerald-700"
    : value >= 0.70
    ? "bg-blue-100 text-blue-700"
    : "bg-amber-100 text-amber-700";
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${cls}`}>
      {pct}% confiança
    </span>
  );
}

export function Classifier() {
  const [descricao, setDescricao] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SuggestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const classify = useCallback(async () => {
    const desc = descricao.trim();
    if (!desc) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/public/ncm/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ descricao: desc }),
      });
      if (res.status === 429) {
        setError("Limite diário de 10 classificações gratuitas atingido. Crie uma conta para mais.");
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Erro ao classificar." }));
        setError(err.detail ?? "Erro ao classificar. Tente novamente.");
        return;
      }
      setResult(await res.json());
    } catch {
      setError("Erro de conexão. Verifique sua internet e tente novamente.");
    } finally {
      setLoading(false);
    }
  }, [descricao]);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <label className="mb-1 block text-sm font-medium text-slate-700">
        Descrição do produto
      </label>
      <div className="flex gap-2">
        <input
          type="text"
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") void classify(); }}
          placeholder="Ex: Carne bovina traseira resfriada, Notebook 16GB, Serviço de instalação elétrica…"
          className="flex-1 rounded-lg border border-slate-300 px-4 py-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          maxLength={300}
          autoFocus
        />
        <button
          type="button"
          onClick={() => void classify()}
          disabled={loading || !descricao.trim()}
          className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Classificando…" : "Classificar"}
        </button>
      </div>
      <p className="mt-1 text-xs text-slate-400">
        Quanto mais detalhada a descrição, maior a precisão.
      </p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-2xl font-bold text-slate-800">{result.ncm}</span>
                <ConfidenceBadge value={result.confidence} />
              </div>
              <p className="mt-0.5 text-sm text-slate-600">{result.ncm_descricao}</p>
              {result.cClassTrib && (
                <p className="mt-1 text-xs font-mono text-blue-700">
                  cClassTrib LC 214: <strong>{result.cClassTrib}</strong>
                </p>
              )}
            </div>
            <Link
              href={`/calculadora?ncm=${result.ncm}`}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700"
            >
              Calcular CBS/IBS →
            </Link>
          </div>

          {result.aviso && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-800">
              ⚠ {result.aviso}
            </div>
          )}

          {!result.aviso && (
            <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-2.5 text-xs text-emerald-800">
              ✓ NCM identificado com alta confiança. Clique em &quot;Calcular CBS/IBS&quot; para ver as alíquotas e gerar o XML para o ERP.
            </div>
          )}
        </div>
      )}

      {/* WhatsApp CTA */}
      <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4">
        <p className="text-sm font-semibold text-red-800">
          NF-e sendo rejeitada pela Rejeição 1024?
        </p>
        <p className="mt-0.5 text-sm text-red-700">
          Quando CST e cClassTrib são incompatíveis, a nota não sai. Nosso time resolve ao vivo.
        </p>
        <a
          href={WA_REJEICAO}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-bold text-white hover:bg-red-700"
        >
          Resolver a Rejeição 1024 no WhatsApp
        </a>
      </div>
    </div>
  );
}
