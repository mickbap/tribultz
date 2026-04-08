"use client";

import { useEffect, useRef, useState } from "react";

// ── Mensagens exibidas enquanto o agente processa ──────────────────────────
// Mistura intencional: progresso técnico | curiosidades fiscais | humor leve
// Ordenação: mantida após shuffle inicial — cada sessão tem sequência diferente.
const THINKING_MESSAGES: string[] = [
  // ── Progresso (tom profissional-amigável) ──────────────────────────────
  "Verificando as regras CBS e IBS para o seu documento...",
  "Consultando a base de regras da LC\u00a0214...",
  "Analisando a classificação tributária do documento...",
  "Cruzando dados com a tabela CEST e ClassTrib...",
  "Validando alíquotas de referência do período de transição...",
  "Processando os requisitos de Split\u00a0Payment...",
  "Verificando evidências de auditoria...",
  "Consultando a NT\u00a02025.002 para confirmar o cálculo...",

  // ── Curiosidades fiscais (💡) ───────────────────────────────────────────
  "💡 CBS + IBS substituem 5 tributos — é a maior reforma fiscal desde 1988.",
  "💡 O IBS é gerido pelo Comitê Gestor de estados e municípios. Federalismo fiscal em ação.",
  "💡 Cashback no IBS: famílias de baixa renda recebem parte do imposto de volta automaticamente.",
  "💡 Split Payment: o imposto é retido na transação — o Fisco recebe antes mesmo do boleto vencer.",
  "💡 A Nota Nacional unifica NF-e, NFC-e e NFS-e em um único padrão nacional.",
  "💡 O período de transição vai de 2026 a 2032 — ainda há tempo de se adaptar.",
  "💡 Alíquota de referência: CBS\u00a00,9% e IBS\u00a017,7%. Somadas chegam a 18,6%.",
  "💡 O IVA Dual brasileiro é único no mundo: tributo federal (CBS) e estadual/municipal (IBS) separados.",
  "💡 CEST identifica substituição tributária; ClassTrib define o regime na reforma. Dois campos, muito poder.",
  "💡 A LC\u00a0227 regulamentou o Split Payment — o banco desconta o imposto antes de repassar o pagamento.",

  // ── Humor leve 😅 ───────────────────────────────────────────────────────
  "☕ Sua consulta está em processamento prioritário. Servida com conformidade e bom humor.",
  "😅 Calculando tributos mais rápido que a SEFAZ... quase lá.",
  "🤓 ICMS, PIS, COFINS, ISS, CSLL... e tem mais. Menos mal que em breve serão só dois.",
  "📚 Relendo a LC\u00a0214 pela milésima vez. Ela ainda não ficou mais curta.",
  "🏛️ A reforma tributária levou 30\u00a0anos de debate. Uns segundos aqui é literalmente nada.",
  "🧮 Se imposto fosse pão, o Brasil seria a maior padaria do planeta.",
  "😤 O contribuinte aguarda. O sistema aguarda. A resposta vem.",
  "🎯 Aplicando as 10 regras determinísticas CBS/IBS com toda a seriedade que elas merecem.",
];

/** Embaralha array no lugar (Fisher-Yates). */
function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

const INTERVAL_MS = 3_800;
const FADE_MS = 280;

/**
 * Exibido no lugar da resposta do assistente enquanto o backend processa.
 * Cicla entre mensagens de progresso, curiosidades fiscais e humor leve.
 */
export function ChatThinkingBubble() {
  // Embaralha na montagem para que cada sessão tenha uma sequência diferente
  const messages = useRef<string[]>(shuffle(THINKING_MESSAGES));
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setInterval(() => {
      // Fase 1: fade out
      setVisible(false);
      // Fase 2: troca mensagem + fade in
      const fadeTimer = setTimeout(() => {
        setIndex((i) => (i + 1) % messages.current.length);
        setVisible(true);
      }, FADE_MS);
      return () => clearTimeout(fadeTimer);
    }, INTERVAL_MS);
    return () => clearInterval(timer);
  }, []);

  return (
    <article
      className="max-w-3xl rounded-xl border border-slate-200 bg-white p-3"
      aria-live="polite"
      aria-label="Assistente processando"
    >
      <p className="mb-2 text-[11px] uppercase tracking-wide text-slate-400">
        assistente
      </p>

      {/* Mensagem rotativa */}
      <p
        className="text-sm text-slate-600 transition-opacity"
        style={{
          opacity: visible ? 1 : 0,
          transitionDuration: `${FADE_MS}ms`,
        }}
      >
        {messages.current[index]}
      </p>

      {/* Pontos animados */}
      <div className="mt-3 flex items-center gap-1.5">
        {[0, 160, 320].map((delay) => (
          <span
            key={delay}
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-tribultz-400"
            style={{ animationDelay: `${delay}ms` }}
            aria-hidden
          />
        ))}
        <span className="ml-1 text-xs text-slate-400">processando</span>
      </div>
    </article>
  );
}
