"use client";

import { openCookiePreferences } from "@/lib/consent";

/**
 * Link "Preferências de cookies" para o rodapé. Reabre o banner de consentimento
 * para o usuário rever/alterar a escolha a qualquer momento (requisito LGPD).
 */
export function CookiePreferencesLink({ className }: { className?: string }) {
  return (
    <button type="button" onClick={() => openCookiePreferences()} className={className}>
      Preferências de cookies
    </button>
  );
}
