"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { track } from "@/lib/analytics";
import {
  getPlanSlug,
  setPlanSlug,
  setSubscriptionStatus,
  setTrialEndsAt,
  setUsage,
  PLAN_FEATURES,
  type PlanSlug,
} from "@/lib/plan";

type BillingInfo = {
  plan_slug: PlanSlug | null;
  plan_name: string | null;
  price_cents: number;
  status: string | null;
  trial_ends_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  max_validations: number | null;
  has_pdf_reports: boolean;
  has_batch: boolean;
  has_dashboard: boolean;
  usage: {
    validations_used: number;
    period: string;
  };
};

type PaymentRecord = {
  id: string;
  amount_cents: number;
  status: string;
  payment_method: string;
  paid_at: string | null;
  created_at: string | null;
};

type UpgradeResponse = {
  subscription_id: string;
  plan_slug: string;
  status: string;
  checkout_url: string | null;
  pix_qr_code: string | null;
  pix_copy_paste: string | null;
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  trial: { label: "Trial", color: "bg-blue-100 text-blue-800" },
  active: { label: "Ativo", color: "bg-green-100 text-green-800" },
  pending: { label: "Pendente", color: "bg-yellow-100 text-yellow-800" },
  past_due: { label: "Atrasado", color: "bg-red-100 text-red-800" },
  cancelled: { label: "Cancelado", color: "bg-gray-100 text-gray-800" },
  expired: { label: "Expirado", color: "bg-red-100 text-red-800" },
};

function formatCurrency(cents: number): string {
  return `R$ ${(cents / 100).toFixed(2).replace(".", ",")}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR");
}

export default function BillingPage() {
  const [info, setInfo] = useState<BillingInfo | null>(null);
  const [payments, setPayments] = useState<PaymentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [upgrading, setUpgrading] = useState(false);
  const [upgradeResult, setUpgradeResult] = useState<UpgradeResponse | null>(null);
  const [pixCopied, setPixCopied] = useState(false);

  const fetchBilling = useCallback(async () => {
    try {
      const [billingData, paymentData] = await Promise.all([
        apiFetch<BillingInfo>("/api/v1/billing/me"),
        apiFetch<PaymentRecord[]>("/api/v1/billing/payments"),
      ]);
      setInfo(billingData);
      setPayments(paymentData);

      // Sync to localStorage
      if (billingData.plan_slug) {
        setPlanSlug(billingData.plan_slug);
        setSubscriptionStatus(billingData.status ?? "trial");
        setTrialEndsAt(billingData.trial_ends_at);
        setUsage({
          validationsUsed: billingData.usage.validations_used,
          aiMessagesUsed: 0,
          period: billingData.usage.period,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar faturamento.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBilling();
  }, [fetchBilling]);

  async function handleUpgrade(targetSlug: PlanSlug) {
    setUpgrading(true);
    setError("");
    try {
      const result = await apiFetch<UpgradeResponse>("/api/v1/billing/upgrade", {
        method: "POST",
        body: JSON.stringify({ plan_slug: targetSlug, billing_type: "PIX" }),
      });
      track("begin_checkout", { plan: targetSlug, context: "upgrade" });
      setUpgradeResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao processar upgrade.");
    } finally {
      setUpgrading(false);
    }
  }

  async function handleCancel() {
    const periodEnd = info?.current_period_end ? formatDate(info.current_period_end) : "";
    const msg = periodEnd
      ? `Tem certeza que deseja cancelar? A cobrança será interrompida, mas você terá acesso até ${periodEnd}.`
      : "Tem certeza que deseja cancelar sua assinatura?";
    if (!confirm(msg)) return;
    try {
      await apiFetch("/api/v1/billing/cancel", { method: "POST" });
      await fetchBilling();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao cancelar.");
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl animate-pulse space-y-4 p-6">
        <div className="h-8 w-48 rounded bg-slate-200" />
        <div className="h-40 rounded bg-slate-100" />
        <div className="h-40 rounded bg-slate-100" />
      </div>
    );
  }

  const currentSlug = info?.plan_slug ?? "trial";
  const currentPlan = PLAN_FEATURES[currentSlug as PlanSlug] ?? PLAN_FEATURES.trial;
  const statusInfo = STATUS_LABELS[info?.status ?? "trial"] ?? STATUS_LABELS.trial;

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-2">
      <h1 className="text-2xl font-bold text-slate-800">Faturamento</h1>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      {/* ── Current plan card ──────────────── */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">
              Plano {currentPlan.name}
            </h2>
            <p className="mt-1 text-2xl font-bold text-slate-900">
              {currentPlan.priceCents === 0 ? "Grátis" : `${formatCurrency(currentPlan.priceCents)}/mês`}
            </p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusInfo.color}`}>
            {statusInfo.label}
          </span>
        </div>

        {info?.status === "trial" && info.trial_ends_at && (
          <p className="mt-2 text-sm text-orange-600">
            Trial expira em: {formatDate(info.trial_ends_at)}
          </p>
        )}

        {info?.current_period_end && info.status === "active" && (
          <p className="mt-2 text-sm text-slate-500">
            Próxima cobrança: {formatDate(info.current_period_end)}
          </p>
        )}
      </div>

      {/* ── Usage meters ──────────────────── */}
      <div className="grid gap-4 md:grid-cols-2">
        <UsageMeter
          label="Validações"
          used={info?.usage.validations_used ?? 0}
          max={info?.max_validations ?? null}
        />
      </div>

      {/* ── Upgrade section ───────────────── */}
      {upgradeResult ? (
        <div className="rounded-lg border border-green-200 bg-green-50 p-6">
          <h3 className="font-semibold text-green-800">Upgrade solicitado!</h3>
          {upgradeResult.pix_qr_code && (
            <div className="mt-4 text-center">
              <img
                src={`data:image/png;base64,${upgradeResult.pix_qr_code}`}
                alt="QR Code PIX"
                className="mx-auto h-48 w-48"
              />
              {upgradeResult.pix_copy_paste && (
                <div className="mt-3">
                  <p className="mb-1 text-xs text-slate-600">Código PIX copia e cola:</p>
                  <div className="flex items-center gap-2 justify-center">
                    <code className="rounded bg-white px-2 py-1 text-xs break-all max-w-xs">
                      {upgradeResult.pix_copy_paste.slice(0, 60)}...
                    </code>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(upgradeResult.pix_copy_paste ?? "");
                        setPixCopied(true);
                        setTimeout(() => setPixCopied(false), 2000);
                      }}
                      className="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700"
                    >
                      {pixCopied ? "Copiado!" : "Copiar"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
          {upgradeResult.checkout_url && (
            <a
              href={upgradeResult.checkout_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-block rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
            >
              Pagar com cartão
            </a>
          )}
        </div>
      ) : (
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-4 font-semibold text-slate-800">Planos disponíveis</h3>
          <div className="grid gap-3 md:grid-cols-3">
            {(["starter", "profissional", "empresarial", "contador"] as PlanSlug[]).map((slug) => {
              const plan = PLAN_FEATURES[slug];
              const isCurrent = slug === currentSlug;
              return (
                <div
                  key={slug}
                  className={`rounded-lg border p-4 ${isCurrent ? "border-blue-300 bg-blue-50" : "border-slate-200"}`}
                >
                  <h4 className="font-medium text-slate-800">{plan.name}</h4>
                  <p className="text-lg font-bold">{formatCurrency(plan.priceCents)}/mês</p>
                  <ul className="mt-2 space-y-1 text-xs text-slate-600">
                    <li>{plan.maxValidations ?? "Ilimitadas"} validações</li>
                    {plan.hasJustificativaFiscal && <li>Justificativa técnica por finding</li>}
                    {plan.hasPdfReports && <li>Relatório PDF</li>}
                    {plan.hasBatch && <li>Validação em lote</li>}
                    {plan.hasDashboard && <li>Dashboard</li>}
                  </ul>
                  {isCurrent ? (
                    <div className="mt-3 space-y-2">
                      <span className="inline-block text-xs font-medium text-blue-700">
                        Plano atual
                      </span>
                      {info?.status === "active" && (
                        <button
                          type="button"
                          onClick={handleCancel}
                          className="block w-full rounded border border-red-200 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50"
                        >
                          Cancelar assinatura
                        </button>
                      )}
                      {info?.status === "cancelled" && info.current_period_end && (
                        <p className="text-xs text-slate-500">
                          Acesso até {formatDate(info.current_period_end)}
                        </p>
                      )}
                    </div>
                  ) : (
                    <button
                      type="button"
                      disabled={upgrading}
                      onClick={() => handleUpgrade(slug)}
                      className="mt-3 w-full rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {upgrading ? "Processando..." : "Fazer upgrade"}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Payment history ───────────────── */}
      {payments.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-3 font-semibold text-slate-800">Histórico de pagamentos</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-slate-500">
                  <th className="pb-2">Data</th>
                  <th className="pb-2">Valor</th>
                  <th className="pb-2">Método</th>
                  <th className="pb-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id} className="border-b last:border-0">
                    <td className="py-2">{formatDate(p.paid_at ?? p.created_at)}</td>
                    <td className="py-2">{formatCurrency(p.amount_cents)}</td>
                    <td className="py-2 capitalize">{p.payment_method === "pix" ? "PIX" : "Cartão"}</td>
                    <td className="py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${
                          p.status === "confirmed"
                            ? "bg-green-100 text-green-700"
                            : p.status === "pending"
                              ? "bg-yellow-100 text-yellow-700"
                              : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {p.status === "confirmed" ? "Pago" : p.status === "pending" ? "Pendente" : p.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Cancelled notice ─────────────── */}
      {info?.status === "cancelled" && info.current_period_end && (
        <div className="rounded-lg border border-orange-200 bg-orange-50 p-4 text-center text-sm text-orange-800">
          Sua assinatura foi cancelada. Você ainda tem acesso até <strong>{formatDate(info.current_period_end)}</strong>.
        </div>
      )}
    </div>
  );
}

function UsageMeter({ label, used, max }: { label: string; used: number; max: number | null }) {
  const isUnlimited = max === null;
  const pct = isUnlimited ? 0 : max > 0 ? Math.min((used / max) * 100, 100) : 0;
  const barColor = pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-orange-400" : "bg-blue-500";

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-medium text-slate-700">{label}</p>
      <p className="mt-1 text-xl font-bold text-slate-900">
        {used} / {isUnlimited ? "Ilimitado" : max}
      </p>
      {!isUnlimited && (
        <div className="mt-2 h-2 w-full rounded-full bg-slate-100">
          <div
            className={`h-2 rounded-full transition-all ${barColor}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}
