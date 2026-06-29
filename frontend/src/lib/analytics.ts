/**
 * Disparo de eventos GA4 (gtag) para o funil de aquisição.
 *
 * No-op no SSR e quando não há consentimento — o gtag respeita o Consent Mode
 * configurado em layout.tsx (analytics_storage começa "denied"). Ver [[consent]].
 *
 * Taxonomia (eventos recomendados do GA4):
 *   - sign_up        → cadastro concluído
 *   - begin_checkout → início de checkout de plano pago (ASAAS)
 *   - generate_lead  → lead de alta intenção (clique no WhatsApp)
 */
type GtagParams = Record<string, unknown>;

export function track(event: string, params: GtagParams = {}): void {
  if (typeof window === "undefined") return;
  window.gtag?.("event", event, params);
}
