"use client";

import type { CSSProperties, ReactNode } from "react";
import { track } from "@/lib/analytics";

/**
 * Link de WhatsApp com tracking de lead (GA4 `generate_lead`).
 *
 * Wrapper client genérico: preserva o estilo de cada CTA (className/style) e só
 * adiciona o disparo do evento no clique. Server components podem renderizá-lo
 * normalmente passando `children` (ícone + label) já renderizados.
 */
export function WhatsAppLink({
  href,
  source,
  className,
  style,
  children,
}: {
  href: string;
  /** Origem do lead, vira parâmetro do evento (ex.: "hero", "rejeicao_1024"). */
  source: string;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
      style={style}
      onClick={() => track("generate_lead", { method: "whatsapp", source })}
    >
      {children}
    </a>
  );
}
