"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * O canal de chat com o agente tributário foi descontinuado por razões de
 * segurança (risco de prompt injection), eficiência operacional e foco
 * na experiência determinística de validação fiscal.
 *
 * Usuários que acessam esta rota diretamente são redirecionados para /jobs.
 */
export default function ChatDeprecatedPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/jobs");
  }, [router]);

  return null;
}
