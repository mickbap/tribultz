import type { Metadata } from "next";
import type { ReactNode } from "react";

// Dashboard autenticado (dados do tenant via /lib/api) — sem conteúdo para
// visitante anônimo, não faz sentido indexar (#503).
export const metadata: Metadata = {
  alternates: { canonical: "/compliance" },
  robots: { index: false, follow: false },
};

export default function ComplianceLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
