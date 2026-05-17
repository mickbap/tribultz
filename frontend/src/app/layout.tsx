import type { Metadata } from "next";
import { Montserrat, Source_Sans_3, Roboto_Mono } from "next/font/google";
import { AppShell } from "@/components/layout/AppShell";
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
const DEFAULT_DESCRIPTION =
  "Evite Rejeição 1024 e penalidades CBS/IBS. Classifique NCM → cClassTrib, valide 18 regras LC 214 e exporte para TOTVS, SAP, Omie e Linx. Compliance auditável para a Reforma Tributária.";

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
  alternates: {
    canonical: SITE_URL,
  },
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
      </body>
    </html>
  );
}
