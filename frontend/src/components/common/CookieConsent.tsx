"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  CONSENT_NEGADO,
  CONSENT_OPEN_EVENT,
  CONSENT_TOTAL,
  getStoredConsent,
  setConsent,
} from "@/lib/consent";

/**
 * Banner de consentimento de cookies em DOIS NÍVEIS, conforme o Guia
 * Orientativo da ANPD ("Cookies e Proteção de Dados Pessoais", out/2022).
 *
 * 1º nível — três ações com o MESMO formato e destaque (o guia rejeita o
 * padrão em que aceitar é botão e recusar é link apagado):
 *   "Rejeitar cookies não necessários" · "Aceitar todos" · "Selecionar cookies"
 *
 * 2º nível — categorias descritas com finalidade e período de retenção,
 * consentimento por finalidade específica, e o que depende de consentimento
 * começa DESATIVADO. Também traz o botão de rejeitar, porque o guia pede a
 * recusa fácil nos dois níveis.
 *
 * Recusar nunca bloqueia a navegação (art. 8º §3º: consentimento livre).
 */

/** Fonte única do que é mostrado ao titular. Mudou aqui, muda a /cookies. */
const CATEGORIAS = [
  {
    id: "essenciais" as const,
    nome: "Estritamente necessários",
    finalidade:
      "Sustentam sessão autenticada, segurança e preferências básicas. Sem eles a plataforma não funciona.",
    retencao: "Não usamos cookies próprios; a sessão fica em armazenamento local do navegador",
    obrigatorio: true,
  },
  {
    id: "analise" as const,
    nome: "Análise de audiência",
    finalidade:
      "Medem uso agregado das páginas (Google Analytics 4) para orientar melhorias. Não formam perfil comportamental nem alimentam publicidade.",
    retencao: "Cookies _ga e _ga_* de terceiro (Google), até 2 anos",
    obrigatorio: false,
  },
];

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);
  const [detalhando, setDetalhando] = useState(false);
  // Desativado por padrão — exigência da ANPD, nunca pré-selecionado.
  const [analise, setAnalise] = useState(false);

  useEffect(() => {
    // localStorage não existe no SSR: decide a visibilidade após montar.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (getStoredConsent() === null) setVisible(true);

    const reopen = () => {
      const atual = getStoredConsent();
      setAnalise(atual?.analise ?? false);
      setDetalhando(false);
      setVisible(true);
    };
    window.addEventListener(CONSENT_OPEN_EVENT, reopen);
    return () => window.removeEventListener(CONSENT_OPEN_EVENT, reopen);
  }, []);

  if (!visible) return null;

  function fechar() {
    setVisible(false);
    setDetalhando(false);
  }

  function rejeitarNaoNecessarios() {
    setConsent(CONSENT_NEGADO);
    fechar();
  }

  function aceitarTodos() {
    setConsent(CONSENT_TOTAL);
    fechar();
  }

  function salvarSelecao() {
    setConsent({ analise });
    fechar();
  }

  const botao =
    "rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600";

  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label="Consentimento de cookies"
      aria-modal="false"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-slate-200 bg-white/95 px-4 py-4 shadow-lg backdrop-blur sm:px-6"
    >
      <div className="mx-auto flex max-w-5xl flex-col gap-4">
        <p className="text-sm text-slate-600">
          Usamos cookies estritamente necessários para o funcionamento da plataforma. Com o
          seu consentimento, usamos também cookies de análise de audiência para entender o
          uso e melhorar o produto. Não usamos cookies de publicidade nem formamos perfis
          comportamentais. Veja a{" "}
          <Link href="/cookies" className="font-medium text-blue-600 underline hover:text-blue-700">
            Política de Cookies
          </Link>{" "}
          ou{" "}
          <Link href="/lgpd" className="font-medium text-blue-600 underline hover:text-blue-700">
            exerça seus direitos como titular
          </Link>
          .
        </p>

        {detalhando && (
          <ul className="flex flex-col gap-3 border-t border-slate-200 pt-3">
            {CATEGORIAS.map((c) => (
              <li key={c.id} className="flex items-start gap-3">
                <input
                  type="checkbox"
                  id={`consent-${c.id}`}
                  className="mt-1 h-4 w-4"
                  checked={c.obrigatorio ? true : analise}
                  disabled={c.obrigatorio}
                  onChange={(e) => setAnalise(e.target.checked)}
                />
                <label htmlFor={`consent-${c.id}`} className="text-sm text-slate-600">
                  <span className="font-medium text-slate-900">{c.nome}</span>
                  {c.obrigatorio && (
                    <span className="ml-2 text-xs text-slate-500">(sempre ativos)</span>
                  )}
                  <br />
                  {c.finalidade}
                  <br />
                  <span className="text-xs text-slate-500">Retenção: {c.retencao}</span>
                </label>
              </li>
            ))}
          </ul>
        )}

        <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
          <button type="button" className={botao} onClick={rejeitarNaoNecessarios}>
            Rejeitar cookies não necessários
          </button>
          {detalhando ? (
            <button type="button" className={botao} onClick={salvarSelecao}>
              Salvar escolhas
            </button>
          ) : (
            <button type="button" className={botao} onClick={() => setDetalhando(true)}>
              Selecionar cookies
            </button>
          )}
          <button type="button" className={botao} onClick={aceitarTodos}>
            Aceitar todos os cookies
          </button>
        </div>
      </div>
    </div>
  );
}
