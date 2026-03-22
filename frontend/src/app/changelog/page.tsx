"use client";

import Link from "next/link";
import data from "@/data/changelog.json";

const typeBadge: Record<string, { label: string; cls: string }> = {
  novo: { label: "Novo", cls: "bg-emerald-100 text-emerald-800" },
  melhoria: { label: "Melhoria", cls: "bg-blue-100 text-blue-800" },
  correcao: { label: "Correcao", cls: "bg-amber-100 text-amber-800" },
};

const scopeBadge: Record<string, string> = {
  frontend: "bg-violet-100 text-violet-700",
  backend: "bg-slate-100 text-slate-700",
};

export default function ChangelogPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-5">
          <div>
            <Link href="/login" className="text-sm text-tribultz-600 hover:underline">
              &larr; Voltar ao login
            </Link>
            <h1 className="mt-1 text-2xl font-bold text-slate-900">Changelog</h1>
            <p className="text-sm text-slate-500">Acompanhe a evolucao da plataforma Tribultz.</p>
          </div>
          <span className="rounded-full bg-tribultz-100 px-3 py-1 text-xs font-semibold text-tribultz-700">
            v0.{data.sprints.length + 5}.0
          </span>
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-6 py-10">
        <div className="relative border-l-2 border-slate-200 pl-8">
          {data.sprints.map((sprint) => (
            <section key={sprint.id} className="relative mb-12 last:mb-0">
              {/* Timeline dot */}
              <div className="absolute -left-[41px] top-0 flex h-5 w-5 items-center justify-center rounded-full border-2 border-tribultz-500 bg-white">
                <div className="h-2 w-2 rounded-full bg-tribultz-500" />
              </div>

              {/* Sprint header */}
              <div className="mb-4">
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-bold text-slate-900">{sprint.title}</h2>
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                    {new Date(sprint.date + "T12:00:00").toLocaleDateString("pt-BR", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                    })}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-600">{sprint.summary}</p>
              </div>

              {/* Entries */}
              <ul className="space-y-3">
                {sprint.entries.map((entry, i) => {
                  const badge = typeBadge[entry.type] ?? typeBadge.novo;
                  return (
                    <li key={i} className="flex items-start gap-3 rounded-lg border border-slate-100 bg-white px-4 py-3 shadow-sm">
                      <span className={`mt-0.5 inline-block shrink-0 rounded px-2 py-0.5 text-xs font-medium ${badge.cls}`}>
                        {badge.label}
                      </span>
                      <div className="flex-1">
                        <p className="text-sm text-slate-800">{entry.text}</p>
                        <div className="mt-1.5 flex gap-1.5">
                          {entry.scope.map((s) => (
                            <span key={s} className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${scopeBadge[s] ?? "bg-slate-100 text-slate-600"}`}>
                              {s}
                            </span>
                          ))}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>

        <footer className="mt-16 border-t border-slate-200 pt-6 text-center text-xs text-slate-400">
          <p>Tribultz &mdash; Conformidade tributaria em tempo de execucao.</p>
          <p className="mt-1">Atualizado automaticamente a cada release.</p>
        </footer>
      </div>
    </main>
  );
}
