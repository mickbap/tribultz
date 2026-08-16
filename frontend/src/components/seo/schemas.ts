/**
 * Schema.org JSON-LD payloads para as páginas pain-point.
 *
 * Mantém os esquemas em um único lugar para garantir consistência de
 * `@id`, URLs e estrutura entre páginas. Cada export retorna um array
 * que vira `@graph` no JsonLd component.
 *
 * Convenção: `@id` usa fragment relativo ao path da página.
 * Ex: a página /pricing referencia `https://tribultz.com.br/pricing#offer-profissional`.
 */

import type { SchemaObject } from "./JsonLd";
import { RULES_COUNT } from "@/lib/validation/rulesMeta";

const SITE_URL = "https://tribultz.com.br";
const ORG_ID = `${SITE_URL}/#org`;

const ORGANIZATION: SchemaObject = {
  "@type": "Organization",
  "@id": ORG_ID,
  "name": "Tribultz",
  "url": SITE_URL,
  "logo": `${SITE_URL}/logo.png`,
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "customer support",
    "availableLanguage": "Portuguese",
  },
};

function faqPage(url: string, qa: Array<{ q: string; a: string }>): SchemaObject {
  return {
    "@type": "FAQPage",
    "@id": `${url}#faq`,
    "mainEntity": qa.map(({ q, a }) => ({
      "@type": "Question",
      "name": q,
      "acceptedAnswer": { "@type": "Answer", "text": a },
    })),
  };
}

// ── /pricing ────────────────────────────────────────────────────────────────

const PRICING_URL = `${SITE_URL}/pricing`;

export const PRICING_SCHEMA: SchemaObject[] = [
  ORGANIZATION,
  {
    "@type": "Product",
    "@id": `${PRICING_URL}#product`,
    "name": "Tribultz — Compliance CBS/IBS",
    "description":
      "Plataforma de validação CBS/IBS, classificação NCM → cClassTrib e " +
      "exportação para ERPs (TOTVS, SAP, Omie, Linx) com evidência auditável.",
    "brand": { "@id": ORG_ID },
    "offers": {
      "@type": "AggregateOffer",
      "priceCurrency": "BRL",
      "lowPrice": "49.90",
      "highPrice": "349.00",
      "offerCount": 4,
      "offers": [
        { "@type": "Offer", "name": "Starter",       "price": "49.90",  "priceCurrency": "BRL", "url": `${PRICING_URL}#starter` },
        { "@type": "Offer", "name": "Profissional", "price": "149.00", "priceCurrency": "BRL", "url": `${PRICING_URL}#profissional` },
        { "@type": "Offer", "name": "Empresarial",  "price": "249.00", "priceCurrency": "BRL", "url": `${PRICING_URL}#empresarial` },
        { "@type": "Offer", "name": "Contador",     "price": "349.00", "priceCurrency": "BRL", "url": `${PRICING_URL}#contador` },
      ],
    },
  },
  faqPage(PRICING_URL, [
    {
      q: "Posso testar a Tribultz antes de assinar?",
      a:
        "Sim. O plano Trial é gratuito e dá acesso a 100 créditos de API e à validação " +
        "completa de até 20 NF-e. Sem cartão de crédito.",
    },
    {
      q: "Como funciona a cobrança da API NCM → cClassTrib?",
      a:
        "A API tem preço pay-per-call dentro do limite do plano. Acima do limite, " +
        "créditos extras podem ser comprados avulsos. O painel mostra consumo em tempo real.",
    },
    {
      q: "Posso mudar de plano a qualquer momento?",
      a:
        "Sim, upgrade e downgrade são imediatos. Diferença proporcional é cobrada ou " +
        "creditada no próximo ciclo.",
    },
    {
      q: "Qual plano é melhor para escritório de contabilidade?",
      a:
        "O plano Contador inclui multi-tenant (até 50 CNPJs de clientes), relatório " +
        "consolidado mensal e SLA de suporte prioritário.",
    },
  ]),
];

// ── /calculadora ────────────────────────────────────────────────────────────

const CALCULADORA_URL = `${SITE_URL}/calculadora`;

export const CALCULADORA_SCHEMA: SchemaObject[] = [
  ORGANIZATION,
  {
    "@type": "WebApplication",
    "@id": `${CALCULADORA_URL}#app`,
    "name": "Calculadora CBS/IBS Tribultz",
    "url": CALCULADORA_URL,
    "applicationCategory": "FinanceApplication",
    "operatingSystem": "Web",
    "isAccessibleForFree": true,
    "offers": { "@type": "Offer", "price": "0", "priceCurrency": "BRL" },
    "description":
      "Calcule CBS e IBS por NCM, UF e CST com alíquotas atualizadas da LC 214. " +
      "Retorna cClassTrib sugerido e base legal.",
  },
  faqPage(CALCULADORA_URL, [
    {
      q: "As alíquotas estão atualizadas com a NT 2025.002 e LC 227?",
      a:
        "Sim. A base de alíquotas é sincronizada com o Convênio ICMS 142/2018, a " +
        "tabela cClassTrib SVRS (atualização de 15/abr/2026) e os regulamentos IBS/CBS " +
        "publicados em 30/abr/2026.",
    },
    {
      q: "A calculadora considera regimes especiais e cesta básica?",
      a:
        "Sim. O cClassTrib resolve o regime aplicável (padrão, reduzido, cesta básica, " +
        "monofásico, imune) e a calculadora aplica o modificador de alíquota correspondente.",
    },
    {
      q: "Posso usar a calculadora sem login?",
      a: "Sim. A versão web é 100% gratuita, sem cadastro, com limite de 100 cálculos por dia por IP.",
    },
    {
      q: "Existe API para integrar essa calculadora ao meu ERP?",
      a:
        "Sim. O endpoint POST /api/v1/public_api/calculate retorna o mesmo resultado em JSON. " +
        "Veja a documentação em /settings/api após o login.",
    },
  ]),
];

// ── /diagnostico ────────────────────────────────────────────────────────────

const DIAGNOSTICO_URL = `${SITE_URL}/diagnostico`;

export const DIAGNOSTICO_SCHEMA: SchemaObject[] = [
  ORGANIZATION,
  {
    "@type": "WebApplication",
    "@id": `${DIAGNOSTICO_URL}#app`,
    "name": "Diagnóstico NF-e CBS/IBS Tribultz",
    "url": DIAGNOSTICO_URL,
    "applicationCategory": "BusinessApplication",
    "operatingSystem": "Web",
    "isAccessibleForFree": true,
    "offers": { "@type": "Offer", "price": "0", "priceCurrency": "BRL" },
    "description":
      `Valide sua NF-e, NFC-e ou NFS-e contra as ${RULES_COUNT} regras da NT 2025.002-RTC. ` +
      "Diagnóstico instantâneo, sem cadastro, evidência auditável.",
  },
  faqPage(DIAGNOSTICO_URL, [
    {
      q: "O que é validado no diagnóstico gratuito?",
      a:
        `São aplicadas ${RULES_COUNT} regras determinísticas: formato CST/cClassTrib/NCM, ` +
        "compatibilidade CST × cClassTrib (Rejeição 1024), cálculo CBS/IBS, " +
        "totais, CEST × ST (Convênio 142/2018), split payment indPag e estrutura XML.",
    },
    {
      q: "Meus dados ficam armazenados?",
      a:
        "Não. O XML enviado pelo formulário público é processado em memória e " +
        "descartado imediatamente. Nenhum CNPJ, valor ou item é persistido. " +
        `Veja a política completa em ${SITE_URL}/data-policy.`,
    },
    {
      q: "O diagnóstico vale como evidência para autuação?",
      a:
        "O relatório inclui timestamp, hash do XML, regra aplicada e base legal. " +
        "Planos pagos exportam o PDF com assinatura digital para auditoria.",
    },
    {
      q: "Há limite de uso gratuito?",
      a: "20 diagnósticos por dia por IP. Sem cadastro. Para volume maior, assine o plano Starter.",
    },
  ]),
];

// ── /classificacao ──────────────────────────────────────────────────────────

const CLASSIFICACAO_URL = `${SITE_URL}/classificacao`;

// ── Blog helpers (Article / BreadcrumbList / Person) ────────────────────────

export function articleSchema({
  url,
  title,
  description,
  publishedAt,
  updatedAt,
  author,
  coverImage,
}: {
  url: string;
  title: string;
  description: string;
  publishedAt: string;
  updatedAt?: string;
  author: { name: string; url: string; jobTitle: string; credentials?: string };
  coverImage?: string;
}): SchemaObject {
  return {
    "@type": "Article",
    "@id": `${url}#article`,
    "headline": title,
    "description": description,
    "url": url,
    "datePublished": publishedAt,
    ...(updatedAt ? { "dateModified": updatedAt } : {}),
    "inLanguage": "pt-BR",
    "author": {
      "@type": "Person",
      "@id": `${author.url}#person`,
      "name": author.name,
      "jobTitle": author.jobTitle,
      ...(author.credentials ? { "description": author.credentials } : {}),
      "worksFor": { "@id": ORG_ID },
    },
    "publisher": { "@id": ORG_ID },
    ...(coverImage ? { "image": coverImage } : {}),
  };
}

export function breadcrumbsSchema(
  items: { name: string; url: string }[],
): SchemaObject {
  return {
    "@type": "BreadcrumbList",
    "@id": `${items[items.length - 1]?.url ?? ""}#breadcrumb`,
    "itemListElement": items.map((item, i) => ({
      "@type": "ListItem",
      "position": i + 1,
      "name": item.name,
      "item": item.url,
    })),
  };
}

export function personSchema({
  name,
  url,
  jobTitle,
  credentials,
  worksFor,
}: {
  name: string;
  url: string;
  jobTitle: string;
  credentials?: string;
  worksFor?: string;
}): SchemaObject {
  return {
    "@type": "Person",
    "@id": `${url}#person`,
    "name": name,
    "url": url,
    "jobTitle": jobTitle,
    ...(credentials ? { "description": credentials } : {}),
    "worksFor": {
      "@type": "Organization",
      "name": worksFor ?? "Tribultz",
      "@id": ORG_ID,
    },
  };
}

// ── /classificacao ──────────────────────────────────────────────────────────

export const CLASSIFICACAO_SCHEMA: SchemaObject[] = [
  ORGANIZATION,
  {
    "@type": "WebApplication",
    "@id": `${CLASSIFICACAO_URL}#app`,
    "name": "Classificador NCM → cClassTrib Tribultz",
    "url": CLASSIFICACAO_URL,
    "applicationCategory": "BusinessApplication",
    "operatingSystem": "Web",
    "isAccessibleForFree": true,
    "offers": { "@type": "Offer", "price": "0", "priceCurrency": "BRL" },
    "description":
      "Sugere o cClassTrib correto para um NCM dado o regime tributário aplicável. " +
      "Evita a Rejeição 1024 antes da emissão da NF-e.",
  },
  faqPage(CLASSIFICACAO_URL, [
    {
      q: "O que é a Rejeição 1024 e como evito?",
      a:
        "A Rejeição 1024 acontece quando o CST informado no XML é incompatível com os " +
        "três primeiros dígitos do cClassTrib (ex: CST 000 com cClassTrib 200034). " +
        "O classificador da Tribultz sugere o cClassTrib correto antes da emissão.",
    },
    {
      q: "A classificação é por NCM ou por descrição do produto?",
      a:
        "Por NCM, com regime tributário escolhido pelo usuário. Para descrições, use o " +
        "endpoint /api/v1/ncm_suggest que aplica IA sobre a descrição e retorna NCM + cClassTrib.",
    },
    {
      q: "A base de cClassTrib está atualizada?",
      a:
        "Sim. Sincronizada com a tabela CST/cClassTrib SVRS publicada em 15/abr/2026 " +
        "e os regulamentos IBS/CBS de 30/abr/2026.",
    },
    {
      q: "Existe API pública para integrar ao meu ERP?",
      a:
        "Sim. Endpoint POST /api/v1/ncm/suggest com autenticação por X-API-Key. " +
        "Veja docs em /settings/api após login.",
    },
  ]),
];
