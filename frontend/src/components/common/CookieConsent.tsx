"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  CONSENT_OPEN_EVENT,
  REFUSE_REDIRECT_URL,
  getStoredConsent,
  setConsent,
} from "@/lib/consent";

/**
 * Banner de consentimento de cookies (LGPD + Google Consent Mode v2).
 *
 * - Aparece automaticamente enquanto o usuário não tiver decidido.
 * - Pode ser reaberto a qualquer momento pelo link "Preferências de cookies"
 *   no rodapé (via evento `CONSENT_OPEN_EVENT`).
 * - "Aceitar": concede o analytics_storage e fecha.
 * - "Recusar": mantém o analytics negado e leva o usuário para fora do site.
 */
export default function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Decidimos a visibilidade só após montar no cliente (localStorage não
    // existe no SSR), evitando hydration mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (getStoredConsent() === null) setVisible(true);

    const reopen = () => setVisible(true);
    window.addEventListener(CONSENT_OPEN_EVENT, reopen);
    return () => window.removeEventListener(CONSENT_OPEN_EVENT, reopen);
  }, []);

  if (!visible) return null;

  function accept() {
    setConsent("granted");
    setVisible(false);
  }

  function refuse() {
    setConsent("denied");
    setVisible(false);
    window.location.href = REFUSE_REDIRECT_URL;
  }

  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label="Consentimento de cookies"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-slate-200 bg-white/95 px-4 py-4 shadow-lg backdrop-blur sm:px-6"
    >
      <div className="mx-auto flex max-w-5xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-600">
          Usamos cookies essenciais para o funcionamento da plataforma e, com seu
          consentimento, cookies de análise (Google Analytics) para entender o uso e
          melhorar o produto. Ao recusar, você será redirecionado para fora do site.
          Veja a{" "}
          <Link href="/cookies" className="font-medium text-blue-600 underline hover:text-blue-700">
            Política de Cookies
          </Link>
          .
        </p>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={refuse}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Recusar e sair
          </button>
          <button
            type="button"
            onClick={accept}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Aceitar
          </button>
        </div>
      </div>
    </div>
  );
}
