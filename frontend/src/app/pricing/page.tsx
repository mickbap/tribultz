"use client";

import Link from "next/link";
import { useState } from "react";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { apiFetch } from "@/lib/api";
import { getToken } from "@/lib/storage";
import { RULES_COUNT, RULES_LABEL } from "@/lib/validation/rulesMeta";

// ── Plan definitions ────────────────────────────────────────────

type Plan = {
  slug: string;
  name: string;
  priceCents: number;
  badge: string | null;
  tagline: string;
  features: string[];
  limits: string;
  cta: string;
  highlighted: boolean;
};

const PLANS: Plan[] = [
  {
    slug: "trial",
    name: "Trial",
    priceCents: 0,
    badge: null,
    tagline: "Comece agora, sem cartão",
    features: [
      "5 validações XML por mês",
      `${RULES_COUNT} regras CBS/IBS`,
      "Diagnóstico gratuito",
      "Calculadora CBS/IBS",
    ],
    limits: "Sem dashboard • Sem PDF • Sem API",
    cta: "Criar conta grátis",
    highlighted: false,
  },
  {
    slug: "starter",
    name: "Starter",
    priceCents: 4990,
    badge: null,
    tagline: "Para autônomos e MEIs",
    features: [
      "10 validações XML por mês",
      `${RULES_COUNT} regras CBS/IBS`,
      "Dashboard de conformidade",
      "Histórico de validações",
    ],
    limits: "Sem PDF auditável • 1 CNPJ",
    cta: "Assinar Starter",
    highlighted: false,
  },
  {
    slug: "profissional",
    name: "Profissional",
    priceCents: 14900,
    badge: "Mais popular",
    tagline: "Para contadores e PMEs",
    features: [
      "500 validações XML por mês",
      "Justificativa técnica + base legal por finding",
      "Relatórios PDF auditáveis",
      "Validação cruzada em lote",
      "API REST + API pública classify (pay-per-call)",
      "Export ERP: TOTVS, SAP, Omie, Linx",
      "Dashboard completo",
    ],
    limits: "1 CNPJ • Sem controle de filiais",
    cta: "Assinar Profissional",
    highlighted: true,
  },
  {
    slug: "empresarial",
    name: "Empresarial",
    priceCents: 24900,
    badge: "Filiais",
    tagline: "Para empresas com filiais",
    features: [
      "2.000 validações XML por mês",
      "Justificativa técnica + base legal por finding",
      "Relatórios PDF auditáveis",
      "Validação cruzada em lote",
      "API REST + API pública classify (pay-per-call)",
      "Export ERP: TOTVS, SAP, Omie, Linx",
      "Controle de até 10 CNPJs de filiais",
    ],
    limits: "Até 10 CNPJs (matriz + filiais)",
    cta: "Assinar Empresarial",
    highlighted: false,
  },
  {
    slug: "contador",
    name: "Contador",
    priceCents: 34900,
    badge: "Multi-CNPJ",
    tagline: "Para escritórios contábeis",
    features: [
      "Validações ilimitadas",
      "Justificativa técnica + base legal por finding",
      "Relatórios PDF e evidências auditáveis",
      "Validação cruzada em lote ilimitada",
      "API REST com webhooks + API pública classify",
      "Export ERP: TOTVS, SAP, Omie, Linx",
      "Gestão de até 50 CNPJs de clientes",
    ],
    limits: "Até 50 CNPJs • SLA 99,9% • Suporte prioritário",
    cta: "Assinar Contador",
    highlighted: false,
  },
];

// ── Helpers ────────────────────────────────────────────────────

function formatPrice(cents: number): string {
  if (cents === 0) return "Grátis";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(cents / 100);
}

function CheckIcon() {
  return (
    <svg
      className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2.5}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

// ── Upgrade modal ──────────────────────────────────────────────

type UpgradeModalProps = {
  plan: Plan;
  onClose: () => void;
};

function UpgradeModal({ plan, onClose }: UpgradeModalProps) {
  const [loading, setLoading] = useState(false);
  const [billingType, setBillingType] = useState<"PIX" | "CREDIT_CARD">("PIX");
  const [result, setResult] = useState<{
    pixQrCode?: string;
    pixCopyPaste?: string;
    checkoutUrl?: string;
    error?: string;
  } | null>(null);

  async function handleUpgrade() {
    setLoading(true);
    setResult(null);
    try {
      const data = (await apiFetch("/api/v1/billing/upgrade", {
        method: "POST",
        body: JSON.stringify({ plan_slug: plan.slug, billing_type: billingType }),
      })) as { pix_qr_code?: string; pix_copy_paste?: string; checkout_url?: string };
      setResult({
        pixQrCode: data.pix_qr_code ?? undefined,
        pixCopyPaste: data.pix_copy_paste ?? undefined,
        checkoutUrl: data.checkout_url ?? undefined,
      });
    } catch (e) {
      setResult({ error: e instanceof Error ? e.message : "Erro ao processar pagamento." });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">
            Assinar {plan.name} — {formatPrice(plan.priceCents)}/mês
          </h2>
          <button
            onClick={onClose}
            className="rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {!result ? (
          <>
            <p className="mb-4 text-sm text-slate-600">
              Escolha a forma de pagamento:
            </p>
            <div className="mb-6 grid grid-cols-2 gap-2">
              {(["PIX", "CREDIT_CARD"] as const).map((type) => (
                <button
                  key={type}
                  onClick={() => setBillingType(type)}
                  className={`rounded-lg border py-2.5 text-xs font-semibold transition ${
                    billingType === type
                      ? "border-tribultz-600 bg-tribultz-50 text-tribultz-700"
                      : "border-slate-200 text-slate-600 hover:border-slate-300"
                  }`}
                >
                  {type === "PIX" ? "PIX" : "Cartão"}
                </button>
              ))}
            </div>
            <button
              onClick={handleUpgrade}
              disabled={loading}
              className="w-full rounded-xl bg-tribultz-600 py-3 font-semibold text-white hover:bg-tribultz-700 disabled:opacity-60"
            >
              {loading ? "Processando…" : `Confirmar ${formatPrice(plan.priceCents)}/mês`}
            </button>
          </>
        ) : result.error ? (
          <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
            {result.error}
          </div>
        ) : result.pixQrCode ? (
          <div className="space-y-4">
            <p className="text-sm font-medium text-slate-700">Escaneie o QR Code PIX:</p>
            <img
              src={`data:image/png;base64,${result.pixQrCode}`}
              alt="QR Code PIX"
              className="mx-auto h-48 w-48 rounded-lg border border-slate-200"
            />
            {result.pixCopyPaste && (
              <div>
                <p className="mb-1 text-xs text-slate-500">Ou copie o código:</p>
                <input
                  readOnly
                  value={result.pixCopyPaste}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700"
                  onClick={(e) => {
                    (e.target as HTMLInputElement).select();
                    navigator.clipboard.writeText(result.pixCopyPaste!);
                  }}
                />
              </div>
            )}
            <p className="text-center text-xs text-slate-400">
              Após o pagamento, sua conta será ativada automaticamente.
            </p>
          </div>
        ) : result.checkoutUrl ? (
          <div className="space-y-4">
            <p className="text-sm text-slate-700">Clique para continuar no ambiente seguro:</p>
            <a
              href={result.checkoutUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full rounded-xl bg-tribultz-600 py-3 text-center font-semibold text-white hover:bg-tribultz-700"
            >
              Pagar com segurança →
            </a>
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ── Plan card ──────────────────────────────────────────────────

type PlanCardProps = {
  plan: Plan;
  isLoggedIn: boolean;
  onUpgrade: (plan: Plan) => void;
};

function PlanCard({ plan, isLoggedIn, onUpgrade }: PlanCardProps) {
  const isFree = plan.priceCents === 0;

  return (
    <div
      className={`relative flex flex-col rounded-2xl border p-6 transition ${
        plan.highlighted
          ? "border-tribultz-500 bg-tribultz-50 shadow-lg ring-1 ring-tribultz-400"
          : "border-slate-200 bg-white shadow-sm hover:shadow-md"
      }`}
    >
      {plan.badge && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="rounded-full bg-tribultz-600 px-3 py-1 text-xs font-bold text-white shadow-sm">
            {plan.badge}
          </span>
        </div>
      )}

      <div className="mb-4">
        <h3 className="text-lg font-bold text-slate-900">{plan.name}</h3>
        <p className="text-sm text-slate-500">{plan.tagline}</p>
      </div>

      <div className="mb-6">
        <span className="text-3xl font-extrabold text-slate-900">
          {formatPrice(plan.priceCents)}
        </span>
        {plan.priceCents > 0 && (
          <span className="ml-1 text-sm text-slate-400">/mês</span>
        )}
      </div>

      <ul className="mb-6 space-y-2 text-sm text-slate-700">
        {plan.features.map((f) => (
          <li key={f} className="flex items-start gap-2">
            <CheckIcon />
            <span>{f}</span>
          </li>
        ))}
      </ul>

      <p className="mb-6 text-xs text-slate-400">{plan.limits}</p>

      <div className="mt-auto">
        {isFree ? (
          <Link
            href="/register"
            className="block w-full rounded-xl border border-tribultz-600 py-2.5 text-center text-sm font-semibold text-tribultz-700 hover:bg-tribultz-50"
          >
            {plan.cta}
          </Link>
        ) : isLoggedIn ? (
          <button
            onClick={() => onUpgrade(plan)}
            className={`w-full rounded-xl py-2.5 text-sm font-semibold transition ${
              plan.highlighted
                ? "bg-tribultz-600 text-white hover:bg-tribultz-700"
                : "border border-slate-200 text-slate-700 hover:border-tribultz-400 hover:text-tribultz-700"
            }`}
          >
            {plan.cta}
          </button>
        ) : (
          <Link
            href={`/register?plan=${plan.slug}`}
            className={`block w-full rounded-xl py-2.5 text-center text-sm font-semibold transition ${
              plan.highlighted
                ? "bg-tribultz-600 text-white hover:bg-tribultz-700"
                : "border border-slate-200 text-slate-700 hover:border-tribultz-400 hover:text-tribultz-700"
            }`}
          >
            {plan.cta}
          </Link>
        )}
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────

export default function PricingPage() {
  const isLoggedIn =
    typeof window !== "undefined" ? Boolean(getToken()) : false;
  const [upgradeTarget, setUpgradeTarget] = useState<Plan | null>(null);

  return (
    <>
      <PublicNavbar />

      <main className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-4 pb-12 pt-16 text-center md:px-6">
          <span className="mb-4 inline-block rounded-full bg-tribultz-100 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-tribultz-700">
            Planos e Preços
          </span>
          <h1 className="mb-4 text-4xl font-extrabold tracking-tight text-slate-900 md:text-5xl">
            Conformidade fiscal sem complicação
          </h1>
          <p className="mx-auto max-w-2xl text-lg text-slate-600">
            Plataforma de validação CBS/IBS para a reforma tributária (LC 214 + LC 227).
            Comece grátis, escale conforme cresce.
          </p>
        </section>

        {/* Plan cards */}
        <section className="mx-auto max-w-6xl px-4 pb-16 md:px-6">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-5">
            {PLANS.map((plan) => (
              <PlanCard
                key={plan.slug}
                plan={plan}
                isLoggedIn={isLoggedIn}
                onUpgrade={(p) => setUpgradeTarget(p)}
              />
            ))}
          </div>
        </section>

        {/* Feature comparison table */}
        <section className="mx-auto max-w-4xl px-4 pb-20 md:px-6">
          <h2 className="mb-8 text-center text-2xl font-bold text-slate-900">
            Comparação detalhada
          </h2>
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-slate-700">Recurso</th>
                  {PLANS.map((p) => (
                    <th
                      key={p.slug}
                      className={`px-4 py-3 text-center font-semibold ${
                        p.highlighted ? "text-tribultz-700" : "text-slate-700"
                      }`}
                    >
                      {p.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {[
                  {
                    label: "Validações XML/mês",
                    // Trial | Starter | Profissional | Empresarial | Contador
                    values: ["5", "10", "500", "2.000", "Ilimitadas"],
                  },
                  {
                    label: "Justificativa técnica + base legal",
                    values: [false, false, true, true, true],
                  },
                  {
                    label: `${RULES_COUNT} regras CBS/IBS`,
                    values: [true, true, true, true, true],
                  },
                  {
                    label: "Dashboard de conformidade",
                    values: [false, true, true, true, true],
                  },
                  {
                    label: "Relatório PDF auditável",
                    values: [false, false, true, true, true],
                  },
                  {
                    label: "Validação cruzada em lote",
                    values: [false, false, true, true, true],
                  },
                  {
                    label: "Acesso à API REST",
                    values: [false, false, true, true, true],
                  },
                  {
                    label: "Controle de filiais (CNPJ)",
                    values: ["—", "—", "—", "Até 10", "Até 50"],
                  },
                  {
                    label: "Suporte prioritário",
                    values: [false, false, false, true, true],
                  },
                ].map((row) => (
                  <tr key={row.label} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-700">{row.label}</td>
                    {row.values.map((val, i) => (
                      <td key={i} className="px-4 py-3 text-center">
                        {typeof val === "boolean" ? (
                          val ? (
                            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100">
                              <svg className="h-3 w-3 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                              </svg>
                            </span>
                          ) : (
                            <span className="inline-block h-0.5 w-4 rounded bg-slate-200" />
                          )
                        ) : (
                          <span className={i === 2 ? "font-semibold text-tribultz-700" : "text-slate-600"}>
                            {val}
                          </span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* FAQ */}
        <section className="mx-auto max-w-3xl px-4 pb-24 md:px-6">
          <h2 className="mb-8 text-center text-2xl font-bold text-slate-900">
            Perguntas frequentes
          </h2>
          <div className="space-y-4">
            {[
              {
                q: "Posso cancelar a qualquer momento?",
                a: "Sim. Sem fidelidade, sem multa. Cancele pelo painel e mantenha o acesso até o fim do período pago.",
              },
              {
                q: "Quais formas de pagamento são aceitas?",
                a: "PIX e cartão de crédito, ambos com aprovação instantânea.",
              },
              {
                q: "O que é a validação cruzada em lote?",
                a: "Envie múltiplas NF-es de uma vez. O sistema detecta duplicatas, inconsistências de CST e calcula um score de risco fiscal.",
              },
            ].map((item) => (
              <div key={item.q} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <p className="mb-2 font-semibold text-slate-900">{item.q}</p>
                <p className="text-sm text-slate-600">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Bottom CTA */}
        <section className="border-t border-slate-200 bg-tribultz-700 py-16 text-center text-white">
          <h2 className="mb-4 text-3xl font-extrabold">Pronto para estar em conformidade?</h2>
          <p className="mb-8 text-tribultz-200">
            {RULES_LABEL}. Evidências auditáveis. Reforma tributária descomplicada.
          </p>
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <Link
              href="/register"
              className="rounded-xl bg-white px-8 py-3 font-bold text-tribultz-700 shadow hover:bg-tribultz-50"
            >
              Criar conta grátis
            </Link>
            <Link
              href="/diagnostico"
              className="rounded-xl border border-tribultz-400 px-8 py-3 font-semibold text-white hover:border-white"
            >
              Ver diagnóstico gratuito →
            </Link>
          </div>
        </section>
      </main>

      {/* Upgrade modal */}
      {upgradeTarget && (
        <UpgradeModal
          plan={upgradeTarget}
          onClose={() => setUpgradeTarget(null)}
        />
      )}
    </>
  );
}
