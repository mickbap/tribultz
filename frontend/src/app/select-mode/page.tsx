"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { API_BASE } from "@/lib/api";
import { getToken, setToken } from "@/lib/storage";
import { setPlanSlug, setSubscriptionStatus } from "@/lib/plan";

type ModeOption = {
  slug: string;
  label: string;
  description: string;
  icon: string;
  color: string;
};

const MODES: ModeOption[] = [
  {
    slug: "trial",
    label: "Trial",
    description: "Experiencia limitada de 2 dias. 3 validacoes, sem dashboard.",
    icon: "\u23F3",
    color: "border-blue-300 bg-blue-50 hover:border-blue-500",
  },
  {
    slug: "starter",
    label: "Starter",
    description: "10 validacoes/mes, dashboard, suporte por email.",
    icon: "\u2B50",
    color: "border-emerald-300 bg-emerald-50 hover:border-emerald-500",
  },
  {
    slug: "profissional",
    label: "Profissional",
    description: "500 validacoes/mes, lote, PDF, suporte prioritario.",
    icon: "\uD83D\uDE80",
    color: "border-violet-300 bg-violet-50 hover:border-violet-500",
  },
  {
    slug: "empresarial",
    label: "Empresarial",
    description: "2.000 validacoes/mes, multi-CNPJ (ate 10 filiais).",
    icon: "\uD83C\uDFE2",
    color: "border-amber-300 bg-amber-50 hover:border-amber-500",
  },
  {
    slug: "contador",
    label: "Contador",
    description: "Validacoes ilimitadas, justificativa tecnica, API access.",
    icon: "\uD83D\uDCCA",
    color: "border-indigo-300 bg-indigo-50 hover:border-indigo-500",
  },
  {
    slug: "admin",
    label: "Administrador",
    description: "Painel administrativo com metricas, financeiro e usuarios.",
    icon: "\uD83D\uDD12",
    color: "border-red-300 bg-red-50 hover:border-red-500",
  },
];

export default function SelectModePage() {
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSelect(slug: string) {
    setLoading(slug);
    setError(null);

    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/select-mode`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ plan_slug: slug }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Erro ${res.status}`);
      }

      const data = await res.json();
      setToken(data.access_token);
      setPlanSlug(data.plan_slug);
      setSubscriptionStatus(slug === "trial" ? "trial" : "active");
      window.dispatchEvent(new Event("tribultz-settings-updated"));

      if (slug === "admin") {
        router.push("/admin");
      } else {
        router.push("/dashboard");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao selecionar modo.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 p-6">
      <div className="w-full max-w-3xl">
        <div className="mb-8 text-center">
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] text-tribultz-600">
            TRIBULTZ
          </p>
          <h1 className="text-2xl font-bold text-slate-900">Selecione o modo de teste</h1>
          <p className="mt-2 text-sm text-slate-500">
            Escolha em qual plano deseja navegar. Para trocar, faca logoff e login novamente.
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-3 text-center text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {MODES.map((mode) => (
            <button
              key={mode.slug}
              type="button"
              disabled={loading !== null}
              onClick={() => handleSelect(mode.slug)}
              className={`group rounded-xl border-2 p-5 text-left transition-all ${mode.color} ${
                loading === mode.slug ? "opacity-70" : ""
              } ${loading !== null && loading !== mode.slug ? "opacity-40" : ""}`}
            >
              <div className="mb-2 text-2xl">{mode.icon}</div>
              <h3 className="text-base font-semibold text-slate-900">{mode.label}</h3>
              <p className="mt-1 text-xs text-slate-600">{mode.description}</p>
              {loading === mode.slug && (
                <p className="mt-2 text-xs font-medium text-slate-500">Carregando...</p>
              )}
            </button>
          ))}
        </div>

        <p className="mt-6 text-center text-xs text-slate-400">
          Acesso restrito a superadmins. Esta tela nao e visivel para usuarios comuns.
        </p>
      </div>
    </main>
  );
}
