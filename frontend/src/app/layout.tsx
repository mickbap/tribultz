import type { Metadata } from "next";
import { Montserrat, Source_Sans_3, Roboto_Mono } from "next/font/google";
import Script from "next/script";
import { AppShell } from "@/components/layout/AppShell";
import CookieConsent from "@/components/common/CookieConsent";
import { CONSENT_STORAGE_KEY } from "@/lib/consent";
import { RULES_COUNT } from "@/lib/validation/rulesMeta";
import "./globals.css";

const montserrat = Montserrat({
  variable: "--font-montserrat",
  subsets: ["latin"],
  display: "swap",
});

const sourceSans = Source_Sans_3({
  variable: "--font-source-sans",
  subsets: ["latin"],
  display: "swap",
});

const robotoMono = Roboto_Mono({
  variable: "--font-roboto-mono",
  subsets: ["latin"],
  display: "swap",
});

const SITE_URL = "https://tribultz.com.br";
const SITE_NAME = "Tribultz";
const GA_MEASUREMENT_ID = "G-KJ986WZ5ZJ";
const DEFAULT_DESCRIPTION =
  `Evite a Rejeição 1024 e penalidades CBS/IBS: valide CST × cClassTrib e ${RULES_COUNT} regras LC 214, calcule CBS/IBS e exporte para TOTVS, SAP, Omie e Linx. Compliance auditável para a Reforma Tributária.`;

export const metadata: Metadata = {
  title: {
    default: "Tribultz | Validação CBS/IBS e cClassTrib — Evite Rejeições de NF-e",
    template: "%s | Tribultz",
  },
  description: DEFAULT_DESCRIPTION,
  keywords: [
    "cClassTrib", "CBS IBS", "NCM cClassTrib", "Rejeição 1024 NF-e",
    "validação CBS IBS", "reforma tributária compliance", "LC 214 CBS IBS",
    "SPED CBS IBS", "API NCM tributário", "split payment 2027",
    "compliance fiscal 2026", "penalidades CBS IBS agosto 2026",
    "software reforma tributária", "validar NF-e CBS IBS",
  ],
  metadataBase: new URL(SITE_URL),
  verification: { google: "dAKEEBuRAkAdRCW7conbkXNO0KCXA6Dab9PGMAfE5cw" },
  openGraph: {
    type: "website",
    locale: "pt_BR",
    url: SITE_URL,
    siteName: SITE_NAME,
    title: "Tribultz | Validação CBS/IBS e cClassTrib — Evite Rejeições de NF-e",
    description: DEFAULT_DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: "Tribultz | Validação CBS/IBS e cClassTrib — Evite Rejeições de NF-e",
    description: DEFAULT_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
  },
  // Sem canonical global (#634): fixá-lo aqui fazia TODA rota que não
  // sobrescrevesse herdar o canonical da home — sinal errado para indexação, e
  // silencioso, porque a página renderiza normalmente. Cada rota pública
  // declara o seu, relativo ao `metadataBase` acima. Rotas da área logada
  // ficam sem canonical de propósito: nenhum é melhor que um apontando para a
  // home. O guard `canonicalMetadata.test.ts` cobre a superfície pública.
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className={`${montserrat.variable} ${sourceSans.variable} ${robotoMono.variable}`}>
        <AppShell>{children}</AppShell>
        <Script
          id="hs-script-loader"
          src="//js.hs-scripts.com/49735644.js"
          strategy="afterInteractive"
        />
        {/* Google Consent Mode v2 — analytics negado por padrão (LGPD).
            Roda antes do gtag.js e respeita a escolha salva pelo usuário. */}
        <Script id="ga-consent-default" strategy="beforeInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            window.gtag = gtag;
            gtag('consent', 'default', {
              ad_storage: 'denied',
              ad_user_data: 'denied',
              ad_personalization: 'denied',
              analytics_storage: 'denied',
            });
            try {
              if (localStorage.getItem('${CONSENT_STORAGE_KEY}') === 'granted') {
                gtag('consent', 'update', {
                  ad_storage: 'granted',
                  ad_user_data: 'granted',
                  ad_personalization: 'granted',
                  analytics_storage: 'granted',
                });
              }
            } catch (e) {}
          `}
        </Script>
        {/* Google tag (gtag.js) */}
        <Script
          id="ga-loader"
          src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`}
          strategy="afterInteractive"
        />
        <Script id="ga-init" strategy="afterInteractive">
          {`
            gtag('js', new Date());
            gtag('config', '${GA_MEASUREMENT_ID}');
          `}
        </Script>
        <CookieConsent />
      </body>
    </html>
  );
}
