/**
 * Cookie consent helpers (Google Consent Mode v2 / LGPD).
 *
 * Analytics são tratados como categoria não essencial: o consentimento começa
 * negado por padrão (ver script `ga-init` em layout.tsx) e só é concedido após
 * ação explícita do usuário no banner. A escolha é persistida em localStorage.
 */

export const CONSENT_STORAGE_KEY = "tribultz-cookie-consent";

/** Evento disparado pelo link do rodapé para reabrir o banner de preferências. */
export const CONSENT_OPEN_EVENT = "tribultz:cookie-preferences";

/**
 * Para onde o usuário é enviado ao recusar os cookies (sai do site).
 * Altere esta URL caso queira outro destino.
 */
export const REFUSE_REDIRECT_URL = "https://6tech.net.br";

export type ConsentChoice = "granted" | "denied";

type GtagFn = (...args: unknown[]) => void;

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: GtagFn;
  }
}

/** Lê a escolha já registrada, ou null se o usuário ainda não decidiu. */
export function getStoredConsent(): ConsentChoice | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(CONSENT_STORAGE_KEY);
    return value === "granted" || value === "denied" ? value : null;
  } catch {
    return null;
  }
}

/** Persiste a escolha e propaga para o Consent Mode do Google. */
export function setConsent(choice: ConsentChoice): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(CONSENT_STORAGE_KEY, choice);
  } catch {
    /* storage indisponível (modo privado / bloqueado) — segue só com gtag */
  }
  window.gtag?.("consent", "update", {
    analytics_storage: choice,
    ad_storage: choice,
    ad_user_data: choice,
    ad_personalization: choice,
  });
}

/** Reabre o banner de preferências de cookies (usado pelo link do rodapé). */
export function openCookiePreferences(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(CONSENT_OPEN_EVENT));
}
