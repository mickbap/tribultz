/**
 * Consentimento de cookies — conformidade com o Guia Orientativo da ANPD
 * ("Cookies e Proteção de Dados Pessoais", out/2022) e com a LGPD.
 *
 * Decisões que vêm do guia, não de preferência nossa:
 *
 * 1. Consentimento POR FINALIDADE ESPECÍFICA (banner de 2º nível). Um único
 *    interruptor para várias finalidades não atende o art. 8º §4º.
 * 2. Cookies baseados em consentimento DESATIVADOS POR PADRÃO — nada de opção
 *    pré-selecionada nem consentimento tácito por continuar navegando.
 * 3. "Qualquer alteração das premissas adotadas para a obtenção do
 *    consentimento macula a hipótese legal adotada, exigindo novo consentimento
 *    pelo titular" — por isso a escolha é versionada e a divergência de versão
 *    equivale a não ter decidido.
 *
 * PUBLICIDADE NÃO EXISTE AQUI, E ISSO É PROPOSITAL. A Tribultz não veicula
 * anúncio nem forma perfil comportamental, e a Política de Cookies afirma isso
 * ao titular. Portanto os sinais `ad_storage`, `ad_user_data` e
 * `ad_personalization` permanecem NEGADOS em qualquer cenário — não há caminho
 * de código que os conceda. Conceder sinal de publicidade sob um banner que só
 * informa análise seria consentimento fora do escopo informado.
 */

/** Versão das premissas do consentimento. Mudou a premissa, muda aqui — e o
 *  titular é consultado de novo (exigência da ANPD, não conveniência). */
export const CONSENT_POLICY_VERSION = "2026-08-20";

export const CONSENT_STORAGE_KEY = "tribultz-cookie-consent";

/** Evento disparado pelo link do rodapé para reabrir as preferências. */
export const CONSENT_OPEN_EVENT = "tribultz:cookie-preferences";

/**
 * Categorias apresentadas ao titular. `essenciais` não é escolha: são os
 * cookies sem os quais a plataforma não funciona (sessão, segurança), e o guia
 * reconhece que aí o consentimento não é a base legal apropriada.
 */
export type ConsentCategories = {
  /** Medição de audiência (Google Analytics 4). Opt-in. */
  analise: boolean;
};

export const CONSENT_NEGADO: ConsentCategories = { analise: false };
export const CONSENT_TOTAL: ConsentCategories = { analise: true };

export type StoredConsent = ConsentCategories & {
  version: string;
  decidedAt: string;
};

type GtagFn = (...args: unknown[]) => void;

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: GtagFn;
  }
}

/**
 * Lê a decisão vigente, ou `null` se o titular ainda não decidiu **sob as
 * premissas atuais**.
 *
 * Valor de versão anterior (inclusive o formato legado `"granted"`/`"denied"`)
 * devolve `null` de propósito: aquele consentimento foi obtido sob premissas
 * diferentes e não vale para as atuais.
 */
export function getStoredConsent(): StoredConsent | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(CONSENT_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      (parsed as StoredConsent).version !== CONSENT_POLICY_VERSION ||
      typeof (parsed as StoredConsent).analise !== "boolean"
    ) {
      return null;
    }
    return parsed as StoredConsent;
  } catch {
    // JSON inválido ou storage bloqueado ⇒ trata como "não decidiu".
    return null;
  }
}

/** Aplica ao Consent Mode. Só `analytics_storage` é governado pela escolha. */
function aplicarNoGtag(categorias: ConsentCategories): void {
  window.gtag?.("consent", "update", {
    analytics_storage: categorias.analise ? "granted" : "denied",
  });
}

/** Persiste a decisão do titular e propaga para o Consent Mode. */
export function setConsent(categorias: ConsentCategories): void {
  if (typeof window === "undefined") return;
  const registro: StoredConsent = {
    ...categorias,
    version: CONSENT_POLICY_VERSION,
    decidedAt: new Date().toISOString(),
  };
  try {
    window.localStorage.setItem(CONSENT_STORAGE_KEY, JSON.stringify(registro));
  } catch {
    /* storage indisponível (modo privado) — segue só com gtag */
  }
  aplicarNoGtag(categorias);
}

/**
 * Revogação (LGPD art. 8º §5º: "procedimento gratuito e facilitado", similar
 * ao usado para obter). Apaga o registro e volta tudo a negado.
 */
export function revokeConsent(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(CONSENT_STORAGE_KEY);
  } catch {
    /* idem */
  }
  aplicarNoGtag(CONSENT_NEGADO);
}

/** Reabre o painel de preferências (link do rodapé). */
export function openCookiePreferences(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(CONSENT_OPEN_EVENT));
}
