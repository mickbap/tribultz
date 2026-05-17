"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/api";

const WA_NUMBER = "5551991881026";
const WA_REJEICAO = `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent("Olá! Estou com Rejeição 1024 na NF-e (cClassTrib incorreto) e preciso de ajuda urgente.")}`;

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

export default function ClassificacaoPage() {
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
    <>
      {/* Hero */}
      <section className="bg-gradient-to-br from-blue-50 to-white px-4 py-16 text-center md:py-20">
        <div className="mx-auto max-w-3xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-red-100 px-4 py-1.5">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            <span className="text-xs font-semibold text-red-700">Penalidades CBS/IBS a partir de agosto/2026</span>
          </div>
          <h1 className="text-3xl font-extrabold leading-tight text-slate-900 md:text-4xl">
            Classifique NCM → cClassTrib<br />
            <span className="text-blue-600">e evite a Rejeição 1024</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-600">
            Descreva o produto em linguagem natural. Nossa IA sugere o NCM correto,
            o cClassTrib da LC 214 e as alíquotas CBS/IBS aplicáveis.
          </p>
          <div className="mx-auto mt-2 flex flex-wrap items-center justify-center gap-4 text-sm text-slate-400">
            <span>10 classificações gratuitas/dia</span>
            <span>·</span>
            <span>Sem login</span>
            <span>·</span>
            <span>LC 214 · NT 2025.002</span>
          </div>
        </div>
      </section>

      {/* Classificador */}
      <section className="mx-auto -mt-6 max-w-2xl px-4 pb-16">
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
        </div>

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
            <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
            </svg>
            Resolver a Rejeição 1024 no WhatsApp
          </a>
        </div>
      </section>

      {/* FAQ SEO */}
      <section className="border-t border-slate-200 bg-white py-16">
        <div className="mx-auto max-w-3xl px-4">
          <h2 className="mb-8 text-2xl font-bold text-slate-900">Perguntas frequentes</h2>
          <div className="space-y-6">
            {[
              {
                q: "O que é cClassTrib e por que ele causa rejeições de NF-e?",
                a: "O cClassTrib é um código de 7 dígitos da LC 214 que define o regime tributário de CBS e IBS de cada produto. Quando ele é incompatível com o CST informado na NF-e, a SEFAZ rejeita a nota com o código 1024. A classificação correta exige mapear o NCM do produto para o regime aplicável (padrão, reduzido, cesta básica, imune, etc.).",
              },
              {
                q: "Quando começam as penalidades por cClassTrib incorreto?",
                a: "As penalidades efetivas por erros de CBS/IBS em NF-e começam em agosto/2026, encerrando o período educacional da Receita Federal. Após essa data, notas com cClassTrib incorreto além de serem rejeitadas podem gerar autuações e multas para o emitente.",
              },
              {
                q: "Como funciona a classificação automática NCM → cClassTrib?",
                a: "Nossa IA analisa a descrição do produto e sugere o NCM mais adequado conforme a TIPI (Decreto 11.158/2022). A partir do capítulo NCM, mapeamos o cClassTrib disponível na tabela oficial SVRS atualizada semanalmente. O resultado inclui um indicador de confiança — valores abaixo de 70% devem ser confirmados com o contador.",
              },
              {
                q: "Posso usar o NCM sugerido diretamente na NF-e?",
                a: "O NCM sugerido é uma referência baseada em IA para agilizar a classificação. Confiança acima de 85% indica alta probabilidade de acerto, mas recomendamos sempre validar com o contador responsável pelo SPED antes de usar em produção. A Tribultz oferece validação completa das 18 regras CBS/IBS para confirmação.",
              },
              {
                q: "Qual a diferença entre NCM e cClassTrib?",
                a: "NCM é o código de 8 dígitos que identifica o produto na Nomenclatura Comum do Mercosul (tabela TIPI). cClassTrib é o código de 7 dígitos da LC 214 que define como esse produto é tributado pelo IBS e CBS na Reforma Tributária. Um mesmo NCM pode ter diferentes cClassTrib dependendo do destino, do beneficiário e do regime fiscal aplicável.",
              },
            ].map((item) => (
              <div key={item.q} className="border-b border-slate-100 pb-6 last:border-0">
                <h3 className="font-semibold text-slate-800">{item.q}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
