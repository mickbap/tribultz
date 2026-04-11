"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AIStatusTimeline, TimelineStage, LogEntry } from "@/components/ai/AIStatusTimeline";

// ── Script de 20 segundos ─────────────────────────────────────────────────────
//
// Cada entrada define:
//   at       — momento em ms em que o evento ocorre
//   stageId  — qual stage é afetado
//   action   — "activate" | "log" | "done" | "error"
//   text     — mensagem de log (apenas para action === "log")

interface ScriptEvent {
  at: number;
  stageId: string;
  action: "activate" | "log" | "done" | "error";
  text?: string;
}

const SCRIPT: ScriptEvent[] = [
  // ── Inicialização (0–2s)
  { at: 0,    stageId: "init",     action: "activate" },
  { at: 300,  stageId: "init",     action: "log", text: "Carregando modelo de agentes CBS/IBS..." },
  { at: 1100, stageId: "init",     action: "log", text: "Contexto tributário injetado. LC 214/2025 + NT 2025.002-RTC ativo." },
  { at: 2000, stageId: "init",     action: "done" },

  // ── Agente de Pesquisa (2–7s)
  { at: 2200, stageId: "pesquisa", action: "activate" },
  { at: 2500, stageId: "pesquisa", action: "log", text: "Conectando ao repositório de legislação fiscal..." },
  { at: 3800, stageId: "pesquisa", action: "log", text: "Localizando LC 214/2025, LC 227 e Emenda Constitucional 132..." },
  { at: 5200, stageId: "pesquisa", action: "log", text: "Consultando ClassTrib SVRS e tabela CST vigente..." },
  { at: 6500, stageId: "pesquisa", action: "log", text: "14 dispositivos legais relevantes identificados e indexados." },
  { at: 7000, stageId: "pesquisa", action: "done" },

  // ── Agente de Auditoria (7–14s)
  { at: 7200,  stageId: "auditoria", action: "activate" },
  { at: 7600,  stageId: "auditoria", action: "log", text: "Carregando base de alíquotas CBS/IBS para 27 UFs..." },
  { at: 9100,  stageId: "auditoria", action: "log", text: "Validando cálculos contra Emenda Constitucional 132..." },
  { at: 10500, stageId: "auditoria", action: "log", text: "Verificando CST 002 (ad rem), CEST e ClassTrib do contribuinte..." },
  { at: 11800, stageId: "auditoria", action: "log", text: "Cruzando Split Payment com base de dados Nota Nacional..." },
  { at: 13200, stageId: "auditoria", action: "log", text: "3 divergências detectadas. Gerando evidências auditáveis..." },
  { at: 14000, stageId: "auditoria", action: "done" },

  // ── Agente de Escrita (14–19s)
  { at: 14200, stageId: "escrita",   action: "activate" },
  { at: 14600, stageId: "escrita",   action: "log", text: "Estruturando parecer técnico com base nas evidências coletadas..." },
  { at: 16000, stageId: "escrita",   action: "log", text: "Redigindo conclusões sobre CBS/IBS aplicáveis ao regime monofásico..." },
  { at: 17400, stageId: "escrita",   action: "log", text: "Inserindo referências legais: art. 12 LC 214, art. 3 LC 227..." },
  { at: 18600, stageId: "escrita",   action: "log", text: "Gerando hash SHA-256 de integridade do documento..." },
  { at: 19200, stageId: "escrita",   action: "done" },

  // ── Conclusão (19–20s)
  { at: 19400, stageId: "conclusao", action: "activate" },
  { at: 19600, stageId: "conclusao", action: "log", text: "Parecer técnico finalizado. Trilha auditável disponível." },
  { at: 19900, stageId: "conclusao", action: "done" },
];

const TOTAL_MS = 20_000;

// ── Stage definitions (initial state — todos idle) ───────────────────────────

function makeInitialStages(): TimelineStage[] {
  return [
    { id: "init",      agentName: "Inicialização",      icon: "⚡", status: "idle", logs: [] },
    { id: "pesquisa",  agentName: "Agente de Pesquisa", icon: "🔍", status: "idle", logs: [] },
    { id: "auditoria", agentName: "Agente de Auditoria",icon: "⚖️", status: "idle", logs: [] },
    { id: "escrita",   agentName: "Agente de Escrita",  icon: "✍️", status: "idle", logs: [] },
    { id: "conclusao", agentName: "Conclusão",          icon: "🏛️", status: "idle", logs: [] },
  ];
}

function newLog(text: string): LogEntry {
  return { id: `${Date.now()}-${Math.random()}`, text, ts: Date.now() };
}

// ── Demo Page ─────────────────────────────────────────────────────────────────

export default function CerebroPage() {
  const [stages, setStages] = useState<TimelineStage[]>(makeInitialStages());
  const [elapsedMs, setElapsedMs] = useState(0);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);

  const startRef = useRef<number | null>(null);
  const rafRef   = useRef<number | null>(null);
  const firedRef = useRef<Set<number>>(new Set());

  // ── Apply a script event to state ──────────────────────────────────────────
  const applyEvent = useCallback((ev: ScriptEvent) => {
    setStages((prev) =>
      prev.map((s) => {
        if (s.id !== ev.stageId) return s;
        switch (ev.action) {
          case "activate":
            return { ...s, status: "active" };
          case "log":
            return { ...s, logs: [...s.logs, newLog(ev.text ?? "")] };
          case "done":
            return { ...s, status: "done" };
          case "error":
            return { ...s, status: "error", logs: [...s.logs, newLog(ev.text ?? "Erro inesperado.")] };
        }
      })
    );
  }, []);

  // ── Animation loop ─────────────────────────────────────────────────────────
  const tick = useCallback(() => {
    if (!startRef.current) return;
    const elapsed = Date.now() - startRef.current;
    setElapsedMs(Math.min(elapsed, TOTAL_MS));

    // Fire events whose `at` time has been crossed
    SCRIPT.forEach((ev, idx) => {
      if (!firedRef.current.has(idx) && elapsed >= ev.at) {
        firedRef.current.add(idx);
        applyEvent(ev);
      }
    });

    if (elapsed >= TOTAL_MS) {
      setDone(true);
      setRunning(false);
      return;
    }

    rafRef.current = requestAnimationFrame(tick);
  }, [applyEvent]);

  // ── Start simulation ───────────────────────────────────────────────────────
  const startSim = useCallback(() => {
    setStages(makeInitialStages());
    setElapsedMs(0);
    setDone(false);
    setRunning(true);
    firedRef.current = new Set();
    startRef.current = Date.now();
    rafRef.current = requestAnimationFrame(tick);
  }, [tick]);

  // ── Cleanup on unmount ─────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  // Auto-start on mount
  useEffect(() => {
    startSim();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-12 flex flex-col items-center">
      {/* Page header */}
      <div className="mb-8 text-center max-w-xl">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-tribultz-500/30 bg-tribultz-500/10 px-4 py-1.5 text-xs font-medium text-tribultz-400">
          <span className="h-1.5 w-1.5 rounded-full bg-tribultz-400 animate-pulse" />
          Stage 2 — Preview do Componente
        </div>
        <h1 className="text-2xl font-bold text-slate-100">
          Cérebro Tribultz
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          Simulação de 20 segundos com 4 agentes CBS/IBS (Pesquisa → Auditoria → Escrita → Conclusão).
          <br />
          Design System Dark Mode · LC 214/2025.
        </p>
      </div>

      {/* Component */}
      <AIStatusTimeline
        stages={stages}
        elapsedMs={elapsedMs}
        maxMs={TOTAL_MS}
        title="Cérebro Tribultz"
        subtitle="Análise fiscal CBS/IBS em tempo real"
        className="w-full max-w-lg"
      />

      {/* Controls */}
      <div className="mt-6 flex gap-3">
        <button
          type="button"
          onClick={startSim}
          disabled={running}
          className="rounded-lg bg-tribultz-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-tribultz-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {running ? "Simulando..." : done ? "▶ Reiniciar" : "▶ Iniciar"}
        </button>
        {running && (
          <button
            type="button"
            onClick={() => {
              if (rafRef.current) cancelAnimationFrame(rafRef.current);
              setRunning(false);
            }}
            className="rounded-lg border border-slate-700 px-5 py-2.5 text-sm font-medium text-slate-400 hover:bg-slate-800 transition-colors"
          >
            ⏸ Pausar
          </button>
        )}
      </div>

      {/* Legend */}
      <div className="mt-8 grid grid-cols-2 gap-3 max-w-lg w-full sm:grid-cols-4">
        {[
          { color: "bg-slate-700",       label: "Idle",       ring: "ring-slate-700" },
          { color: "bg-tribultz-500",    label: "Active",     ring: "ring-tribultz-500/50" },
          { color: "bg-emerald-500",     label: "Done",       ring: "ring-emerald-500/50" },
          { color: "bg-red-500",         label: "Error",      ring: "ring-red-500/50" },
        ].map(({ color, label, ring }) => (
          <div key={label} className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900 px-3 py-2">
            <span className={`h-3 w-3 flex-shrink-0 rounded-full ${color} ring-2 ring-offset-1 ring-offset-slate-900 ${ring}`} />
            <span className="text-xs text-slate-500">{label}</span>
          </div>
        ))}
      </div>

      {/* Integration note */}
      <div className="mt-6 max-w-lg w-full rounded-xl border border-slate-800 bg-slate-900/60 px-5 py-4">
        <p className="text-xs font-semibold text-slate-400 mb-2">Integração com CrewAI (produção)</p>
        <pre className="text-[11px] text-slate-600 leading-relaxed overflow-x-auto font-mono">{`// O Agente consome XML fiscal + documentação técnica
// (LC 214/2025, NT 2025.002-RTC, ClassTrib SVRS)
// e formula, no linguajar do contador, a evidência
// auditável perfeita para cada divergência encontrada.
//
// Streaming via SSE: cada estágio do CrewAI emite eventos
// que atualizam stages[] em tempo real.
<AIStatusTimeline
  stages={crewStages}       // atualizado via SSE do CrewAI
  elapsedMs={Date.now() - startedAt}
  maxMs={45_000}            // timeout máximo CrewAI
/>`}</pre>
      </div>
    </div>
  );
}
