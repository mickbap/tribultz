"use client";

import { useEffect, useRef } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

export type StageStatus = "idle" | "active" | "done" | "error";

export interface LogEntry {
  id: string;
  text: string;
  ts: number; // epoch ms
}

export interface TimelineStage {
  id: string;
  agentName: string; // ex: "Agente de Pesquisa"
  icon: string;      // emoji displayed on the dot
  status: StageStatus;
  logs: LogEntry[];  // messages emitted during this stage
}

export interface AIStatusTimelineProps {
  stages: TimelineStage[];
  elapsedMs: number;   // elapsed time in milliseconds
  maxMs: number;       // expected maximum (for progress bar)
  title?: string;
  subtitle?: string;
  className?: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function statusLabel(status: StageStatus): string {
  switch (status) {
    case "idle":   return "Aguardando";
    case "active": return "Processando";
    case "done":   return "Concluído";
    case "error":  return "Erro";
  }
}

// ── Brain Wave visual ─────────────────────────────────────────────────────────

function BrainWave({ active }: { active: boolean }) {
  const bars = [0.4, 0.7, 1, 0.6, 0.9, 0.5, 0.8, 1, 0.6, 0.4, 0.7, 1, 0.5];
  return (
    <div className="flex items-center gap-[3px] h-6">
      {bars.map((h, i) => (
        <span
          key={i}
          className={`inline-block w-[3px] rounded-full transition-all duration-500 ${
            active
              ? "bg-tribultz-400 animate-brain-wave"
              : "bg-slate-600"
          }`}
          style={{
            height: `${Math.round(h * 22)}px`,
            animationDelay: `${i * 80}ms`,
          }}
        />
      ))}
    </div>
  );
}

// ── Stage Dot ─────────────────────────────────────────────────────────────────

function StageDot({ status, icon }: { status: StageStatus; icon: string }) {
  if (status === "done") {
    return (
      <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-emerald-500/20 ring-1 ring-emerald-500/50 text-sm animate-fade-in">
        <svg className="h-4 w-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
        </svg>
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-red-500/20 ring-1 ring-red-500/50 text-sm">
        <svg className="h-4 w-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </span>
    );
  }
  if (status === "active") {
    return (
      <span className="relative flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-tribultz-500/20 ring-1 ring-tribultz-500/60 animate-pulse-glow text-base">
        {/* Outer pulse ring */}
        <span className="absolute inset-0 rounded-full animate-ping bg-tribultz-500/20" />
        <span className="relative">{icon}</span>
      </span>
    );
  }
  // idle
  return (
    <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-slate-800 ring-1 ring-slate-700 text-base opacity-40">
      {icon}
    </span>
  );
}

// ── Log Message Row ───────────────────────────────────────────────────────────

function LogRow({ text, isLast, isActive }: { text: string; isLast: boolean; isActive: boolean }) {
  return (
    <p className={`text-xs leading-relaxed font-mono animate-slide-up-fade ${
      isLast && isActive ? "text-slate-200" : "text-slate-500"
    }`}>
      <span className="text-tribultz-500 select-none mr-1">›</span>
      {text}
      {isLast && isActive && (
        <span className="ml-0.5 inline-block w-[6px] h-[11px] bg-tribultz-400 rounded-sm animate-blink-cursor align-middle" />
      )}
    </p>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function AIStatusTimeline({
  stages,
  elapsedMs,
  maxMs,
  title = "Cérebro Tribultz",
  subtitle = "Agentes CBS/IBS em execução",
  className = "",
}: AIStatusTimelineProps) {
  const logRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom whenever logs change
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  });

  const progressPct = Math.min(100, (elapsedMs / maxMs) * 100);
  const isComplete = stages.every((s) => s.status === "done" || s.status === "error");
  const hasError = stages.some((s) => s.status === "error");
  const activeStage = stages.find((s) => s.status === "active");

  return (
    <div
      className={`relative flex flex-col rounded-2xl border border-slate-700/60 bg-slate-950 text-slate-100 shadow-2xl shadow-black/60 overflow-hidden ${className}`}
    >
      {/* ── Ambient glow ── */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-tribultz-900/20 to-transparent" />

      {/* ── Header ───────────────────────────────────────────────────────────── */}
      <div className="relative flex items-center justify-between gap-4 border-b border-slate-800/80 px-5 py-4">
        <div className="flex items-center gap-3">
          {/* Animated brain icon */}
          <div className={`relative flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl ${
            isComplete && !hasError
              ? "bg-emerald-500/20 ring-1 ring-emerald-500/40"
              : hasError
              ? "bg-red-500/20 ring-1 ring-red-500/40"
              : "bg-tribultz-600/30 ring-1 ring-tribultz-500/40"
          }`}>
            {isComplete && !hasError ? (
              <svg className="h-5 w-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            ) : (
              <>
                {!isComplete && (
                  <span className="absolute inset-0 rounded-xl border border-tribultz-500/30 animate-spin-slow" />
                )}
                <span className="text-xl">🧠</span>
              </>
            )}
          </div>

          <div>
            <p className="text-sm font-semibold text-slate-100">{title}</p>
            <p className="text-xs text-slate-500">{subtitle}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Brain wave visualizer */}
          <BrainWave active={!isComplete} />

          {/* Elapsed timer */}
          <div className="rounded-lg bg-slate-800/80 px-3 py-1.5 text-center">
            <p className="font-mono text-sm font-bold text-tribultz-300">
              {fmtElapsed(elapsedMs)}
            </p>
            <p className="text-[10px] text-slate-600 leading-none mt-0.5">
              {isComplete ? "total" : "decorrido"}
            </p>
          </div>
        </div>
      </div>

      {/* ── Progress bar ─────────────────────────────────────────────────────── */}
      <div className="px-5 pt-3 pb-0">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[11px] text-slate-500 font-medium tracking-wide uppercase">
            {isComplete && !hasError
              ? "Análise concluída"
              : hasError
              ? "Erro na análise"
              : activeStage
              ? activeStage.agentName
              : "Inicializando..."}
          </span>
          <span className="text-[11px] font-mono text-slate-500">
            {Math.round(progressPct)}%
          </span>
        </div>
        <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
          {/* Fill */}
          <div
            className={`h-full rounded-full transition-all duration-700 ease-out ${
              isComplete && !hasError
                ? "bg-emerald-500"
                : hasError
                ? "bg-red-500"
                : "bg-tribultz-500"
            }`}
            style={{ width: `${progressPct}%` }}
          />
          {/* Shimmer on active */}
          {!isComplete && (
            <div
              className="absolute inset-y-0 w-1/4 rounded-full bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer-right"
              style={{ left: 0 }}
            />
          )}
        </div>
      </div>

      {/* ── Timeline ─────────────────────────────────────────────────────────── */}
      <div ref={logRef} className="flex-1 overflow-y-auto scroll-thin px-5 py-4 max-h-[340px]">
        <div className="relative flex flex-col gap-0">
          {stages.map((stage, idx) => {
            const isLast = idx === stages.length - 1;
            const isActive = stage.status === "active";
            const isDone = stage.status === "done";
            const isIdle = stage.status === "idle";

            return (
              <div key={stage.id} className="relative flex gap-4">
                {/* Vertical connector line */}
                {!isLast && (
                  <div
                    className={`absolute left-[17px] top-9 bottom-0 w-px transition-colors duration-700 ${
                      isDone ? "bg-emerald-500/40" : isActive ? "bg-tribultz-500/30" : "bg-slate-800"
                    }`}
                    style={{ minHeight: "16px" }}
                  />
                )}

                {/* Dot */}
                <div className="relative z-10 flex-shrink-0 pb-5">
                  <StageDot status={stage.status} icon={stage.icon} />
                </div>

                {/* Content */}
                <div className="flex-1 pb-5 min-w-0">
                  {/* Stage header */}
                  <div className="flex items-center gap-2 mt-2 mb-1.5">
                    <span className={`text-sm font-semibold transition-colors duration-500 ${
                      isDone ? "text-emerald-400"
                      : isActive ? "text-tribultz-300"
                      : "text-slate-600"
                    }`}>
                      {stage.agentName}
                    </span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium tracking-wide transition-all duration-500 ${
                      isDone
                        ? "bg-emerald-500/15 text-emerald-400"
                        : isActive
                        ? "bg-tribultz-500/15 text-tribultz-400 animate-pulse"
                        : "bg-slate-800 text-slate-600"
                    }`}>
                      {statusLabel(stage.status)}
                    </span>
                  </div>

                  {/* Log messages */}
                  {stage.logs.length > 0 && (
                    <div className="flex flex-col gap-1">
                      {isIdle ? (
                        <p className="text-xs text-slate-700 font-mono">
                          <span className="text-slate-800 mr-1">›</span>
                          Aguardando turno...
                        </p>
                      ) : (
                        stage.logs.map((log, li) => (
                          <LogRow
                            key={log.id}
                            text={log.text}
                            isLast={li === stage.logs.length - 1}
                            isActive={isActive}
                          />
                        ))
                      )}
                    </div>
                  )}

                  {/* Idle placeholder */}
                  {isIdle && stage.logs.length === 0 && (
                    <p className="text-xs text-slate-700 font-mono">
                      <span className="text-slate-800 mr-1">›</span>
                      Aguardando turno...
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Footer ───────────────────────────────────────────────────────────── */}
      <div className="border-t border-slate-800/80 px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          {/* Animated dots indicator */}
          {!isComplete ? (
            <>
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="inline-block h-1.5 w-1.5 rounded-full bg-tribultz-500 animate-dot-flicker"
                  style={{ animationDelay: `${i * 200}ms` }}
                />
              ))}
              <span className="ml-1 text-xs text-slate-600">
                Processando · LC 214/2025
              </span>
            </>
          ) : (
            <span className={`text-xs font-medium ${hasError ? "text-red-400" : "text-emerald-400"}`}>
              {hasError ? "Erro detectado — verifique os logs" : "Trilha auditável gerada com sucesso"}
            </span>
          )}
        </div>
        <span className="text-[10px] text-slate-700 font-mono">
          tribultz v0.2
        </span>
      </div>
    </div>
  );
}
