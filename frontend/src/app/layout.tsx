import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AppShell } from "@/components/layout/AppShell";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
