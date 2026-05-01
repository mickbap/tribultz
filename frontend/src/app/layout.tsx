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
  "Plataforma de inteligência fiscal para a reforma tributária brasileira. Validação determinística CBS/IBS, memória de precedentes e trilha auditável.";

export const metadata: Metadata = {
  title: {
    default: "Tribultz | Inteligência Fiscal para a Reforma Tributária",
    template: "%s | Tribultz",
  },
  description: DEFAULT_DESCRIPTION,
  metadataBase: new URL(SITE_URL),
  openGraph: {
    type: "website",
    locale: "pt_BR",
    url: SITE_URL,
    siteName: SITE_NAME,
    title: "Tribultz | Inteligência Fiscal para a Reforma Tributária",
    description: DEFAULT_DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: "Tribultz | Inteligência Fiscal para a Reforma Tributária",
    description: DEFAULT_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
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
