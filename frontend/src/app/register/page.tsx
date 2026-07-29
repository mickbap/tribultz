"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Turnstile, type TurnstileInstance } from "@marsidev/react-turnstile";
import { Toast } from "@/components/common/Toast";
import { registerWithApi } from "@/lib/api";
import { track } from "@/lib/analytics";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

type PlanSlug = "trial" | "starter" | "profissional" | "empresarial" | "contador";

const PLANS: { slug: PlanSlug; name: string; price: string; features: string[]; highlight?: boolean }[] = [
  {
    slug: "trial",
    name: "Trial",
    price: "Grátis por 3 dias",
    features: ["5 validações", "Download TXT", "Sem dashboard", "Sem suporte"],
  },
  {
    slug: "starter",
    name: "Starter",
    price: "R$ 49,90/mês",
    features: ["10 validações/mês", "Dashboard", "Suporte por email"],
  },
  {
    slug: "profissional",
    name: "Profissional",
    price: "R$ 149,00/mês",
    features: ["500 validações/mês", "Relatório PDF", "Validação em lote", "Suporte prioritário"],
    highlight: true,
  },
  {
    slug: "empresarial",
    name: "Empresarial",
    price: "R$ 249,00/mês",
    features: ["2.000 validações/mês", "Relatório PDF", "Validação em lote", "Até 10 CNPJs (filiais)"],
  },
  {
    slug: "contador",
    name: "Contador",
    price: "R$ 349,00/mês",
    features: ["Validações ilimitadas", "Justificativa técnica por finding", "Relatório PDF", "Multi-CNPJ", "API access", "Suporte prioritário"],
  },
];

function formatCnpj(value: string): string {
  // CNPJ alfanumérico (RFB, produção 27/07/2026): as 12 primeiras posições
  // aceitam letras, só os 2 dígitos verificadores finais são numéricos.
  const chars = value.replace(/[^A-Za-z0-9]/g, "").toUpperCase().slice(0, 14);
  if (chars.length <= 2) return chars;
  if (chars.length <= 5) return `${chars.slice(0, 2)}.${chars.slice(2)}`;
  if (chars.length <= 8) return `${chars.slice(0, 2)}.${chars.slice(2, 5)}.${chars.slice(5)}`;
  if (chars.length <= 12) return `${chars.slice(0, 2)}.${chars.slice(2, 5)}.${chars.slice(5, 8)}/${chars.slice(8)}`;
  return `${chars.slice(0, 2)}.${chars.slice(2, 5)}.${chars.slice(5, 8)}/${chars.slice(8, 12)}-${chars.slice(12)}`;
}

function formatPhone(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 11);
  if (digits.length <= 2) return digits.length ? `(${digits}` : "";
  if (digits.length <= 7) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

function normalizeCnpj(formatted: string): string {
  return formatted.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
}

export default function RegisterPage() {
  const [step, setStep] = useState<1 | 2>(1);
  const [planSlug, setPlanSlug] = useState<PlanSlug>("trial");
  const [accountType, setAccountType] = useState<"empresa" | "contador">("empresa");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [cnpj, setCnpj] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [billingType, setBillingType] = useState<"PIX" | "CREDIT_CARD">("PIX");
  const [lgpdConsent, setLgpdConsent] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [refundPolicyAccepted, setRefundPolicyAccepted] = useState(false);
  const [multiTenantConsent, setMultiTenantConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [registered, setRegistered] = useState(false);
  const [paymentData, setPaymentData] = useState<{ checkout_url?: string; pix_qr_code?: string; pix_copy_paste?: string } | null>(null);
  const [toast, setToast] = useState<{ tone: "success" | "error"; msg: string } | null>(null);
  const [captchaToken, setCaptchaToken] = useState("");
  // Proveniência comercial (RFC-0025): captura o código do link ?partner=/?ref=.
  const [partnerCode, setPartnerCode] = useState("");
  // Atribuição de diagnóstico gratuito (Escopo A): captura o id do link ?diag=
  // no PDF. Independente do Partner acima — não é o mesmo conceito.
  const [diagId, setDiagId] = useState("");
  const turnstileRef = useRef<TurnstileInstance>(null);
  const captchaConfigured = Boolean(TURNSTILE_SITE_KEY?.trim());

  const isPaidPlan = planSlug !== "trial";

  useEffect(() => {
    // Lê ?partner=/?ref= e ?diag= no carregamento (client-only, seguro no build).
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const code = params.get("partner") ?? params.get("ref");
    if (code) setPartnerCode(code.trim().toUpperCase());
    const diag = params.get("diag");
    if (diag) setDiagId(diag.trim());
  }, []);

  function validateStep1(): boolean {
    if (!fullName.trim() || !email.trim() || !password.trim()) {
      setToast({ tone: "error", msg: "Preencha todos os campos obrigatórios." });
      return false;
    }
    const normalized = normalizeCnpj(cnpj);
    if (normalized.length !== 14) {
      setToast({ tone: "error", msg: "CNPJ deve ter 14 caracteres (12 alfanuméricos + 2 dígitos verificadores)." });
      return false;
    }
    if (password !== confirmPassword) {
      setToast({ tone: "error", msg: "Senhas não conferem." });
      return false;
    }
    if (password.length < 8) {
      setToast({ tone: "error", msg: "Senha deve ter no mínimo 8 caracteres." });
      return false;
    }
    if (!lgpdConsent) {
      setToast({ tone: "error", msg: "Você deve aceitar a Política de Privacidade para prosseguir." });
      return false;
    }
    if (!termsAccepted) {
      setToast({ tone: "error", msg: "Você deve aceitar os Termos de Uso para prosseguir." });
      return false;
    }
    if (!refundPolicyAccepted) {
      setToast({ tone: "error", msg: "Você deve aceitar a Política de Reembolso para prosseguir." });
      return false;
    }
    if ((planSlug === "empresarial" || planSlug === "contador") && !multiTenantConsent) {
      setToast({ tone: "error", msg: "Você deve aceitar o termo de Responsabilidade Multi-Tenant para prosseguir." });
      return false;
    }
    if (!captchaConfigured) {
      setToast({ tone: "error", msg: "CAPTCHA indisponível no momento. Contate o suporte." });
      return false;
    }
    if (!captchaToken) {
      setToast({ tone: "error", msg: "Aguarde a verificação de segurança (CAPTCHA)." });
      return false;
    }
    return true;
  }

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setToast(null);

    if (!validateStep1()) return;

    setLoading(true);
    try {
      const result = await registerWithApi({
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        cnpj: normalizeCnpj(cnpj),
        phone: phone.replace(/\D/g, ""),
        account_type: accountType,
        plan_slug: planSlug,
        billing_type: billingType,
        lgpd_consent: lgpdConsent,
        terms_accepted: termsAccepted,
        refund_policy_accepted: refundPolicyAccepted,
        tenant_slug: "",
        captcha_token: captchaToken,
        partner_code: partnerCode || undefined,
        diag_id: diagId || undefined,
      });

      track("sign_up", { method: accountType, plan: planSlug });

      if (isPaidPlan && (result.checkout_url || result.pix_qr_code)) {
        track("begin_checkout", { plan: planSlug, payment: billingType });
        setPaymentData({
          checkout_url: result.checkout_url,
          pix_qr_code: result.pix_qr_code,
          pix_copy_paste: result.pix_copy_paste,
        });
        setStep(2);
      } else {
        setRegistered(true);
      }
    } catch (err) {
      setToast({
        tone: "error",
        msg: err instanceof Error ? err.message : "Falha ao registrar.",
      });
      setCaptchaToken("");
      turnstileRef.current?.reset();
    } finally {
      setLoading(false);
    }
  }

  // ── Success screen (trial) ──────────────────────────────────
  if (registered) {
    return (
      <main className="grid min-h-screen place-items-center p-6">
        <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-2xl">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-blue-100">
            <svg className="h-7 w-7 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Verifique seu email</h1>
          <p className="mt-2 text-sm text-slate-600">
            Enviamos um link de confirmação para <strong>{email}</strong>.
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Clique no link no email para ativar sua conta. O link expira em 24 horas.
          </p>
          <Link
            href="/login"
            className="mt-6 inline-block rounded-lg bg-tribultz-600 px-6 py-2.5 font-semibold text-white hover:bg-tribultz-700"
          >
            Ir para login
          </Link>
        </section>
      </main>
    );
  }

  // ── Step 2: Payment ─────────────────────────────────────────
  if (step === 2 && paymentData) {
    return (
      <main className="grid min-h-screen place-items-center p-6">
        <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-2xl">
          <h1 className="text-2xl font-bold text-slate-900">Finalizar pagamento</h1>
          <p className="mt-1 text-sm text-slate-500">
            Plano <strong>{PLANS.find((p) => p.slug === planSlug)?.name}</strong> — {PLANS.find((p) => p.slug === planSlug)?.price}
          </p>

          {paymentData.pix_qr_code ? (
            <div className="mt-6 space-y-4">
              <p className="text-sm font-medium text-slate-700">Escaneie o QR Code com seu app de banco:</p>
              <div className="flex justify-center">
                <img
                  src={`data:image/png;base64,${paymentData.pix_qr_code}`}
                  alt="QR Code PIX"
                  className="h-48 w-48 rounded-lg border border-slate-200"
                />
              </div>
              {paymentData.pix_copy_paste && (
                <div>
                  <p className="mb-1 text-xs text-slate-500">Ou copie o código PIX:</p>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      readOnly
                      value={paymentData.pix_copy_paste}
                      className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-xs"
                    />
                    <button
                      type="button"
                      onClick={() => { navigator.clipboard.writeText(paymentData.pix_copy_paste ?? ""); setToast({ tone: "success", msg: "Código copiado!" }); }}
                      className="whitespace-nowrap rounded-lg bg-tribultz-600 px-3 py-2 text-xs font-semibold text-white hover:bg-tribultz-700"
                    >
                      Copiar
                    </button>
                  </div>
                </div>
              )}
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                <p className="text-xs text-blue-800">
                  Após a confirmação do pagamento, enviaremos um email de boas-vindas com o link de ativação da sua conta.
                </p>
              </div>
            </div>
          ) : paymentData.checkout_url ? (
            <div className="mt-6 space-y-4">
              <p className="text-sm text-slate-600">Complete o pagamento no ambiente seguro do Asaas:</p>
              <a
                href={paymentData.checkout_url}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full rounded-lg bg-tribultz-600 px-4 py-2.5 text-center font-semibold text-white hover:bg-tribultz-700"
              >
                Pagar com cartão de crédito
              </a>
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                <p className="text-xs text-blue-800">
                  Após a confirmação do pagamento, enviaremos um email de boas-vindas com o link de ativação da sua conta.
                </p>
              </div>
            </div>
          ) : null}

          <p className="mt-4 text-center text-sm text-slate-500">
            <Link href="/login" className="font-medium text-tribultz-700 hover:underline">
              Voltar ao login
            </Link>
          </p>
        </section>
        {toast ? <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} /> : null}
      </main>
    );
  }

  // ── Step 1: Registration form ───────────────────────────────
  return (
    <main className="grid min-h-screen place-items-center p-6">
      <section className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-8 shadow-2xl">
        <h1 className="text-2xl font-bold text-slate-900">Criar conta</h1>
        <p className="mt-1 text-sm font-medium text-tribultz-700">Garanta sua conformidade fiscal antes que a reforma tributária te pegue de surpresa.</p>
        {partnerCode && (
          <p className="mt-2 inline-block rounded-full bg-tribultz-50 px-3 py-1 text-xs font-medium text-tribultz-700">
            Indicação detectada no link: <span className="font-mono">{partnerCode}</span>
          </p>
        )}

        {/* Plan picker */}
        <fieldset className="mt-6 space-y-3">
          <legend className="text-sm font-medium text-slate-700">Escolha seu plano</legend>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {PLANS.map((plan) => (
              <label
                key={plan.slug}
                className={`relative flex cursor-pointer flex-col rounded-lg border p-3 text-sm transition ${
                  planSlug === plan.slug
                    ? "border-tribultz-500 bg-tribultz-50 ring-1 ring-tribultz-500"
                    : "border-slate-200 hover:border-slate-300"
                } ${plan.highlight ? "sm:ring-2 sm:ring-tribultz-200" : ""}`}
              >
                <input
                  type="radio"
                  name="plan"
                  value={plan.slug}
                  checked={planSlug === plan.slug}
                  onChange={() => {
                    setPlanSlug(plan.slug);
                    setAccountType(plan.slug === "contador" ? "contador" : "empresa");
                  }}
                  className="sr-only"
                />
                {plan.highlight && (
                  <span className="absolute -top-2 right-2 rounded-full bg-tribultz-600 px-2 py-0.5 text-[10px] font-bold text-white">
                    Popular
                  </span>
                )}
                <span className="font-semibold text-slate-900">{plan.name}</span>
                <span className="mt-0.5 text-xs font-medium text-tribultz-700">{plan.price}</span>
                <ul className="mt-2 space-y-0.5">
                  {plan.features.map((f) => (
                    <li key={f} className="text-[11px] text-slate-500">• {f}</li>
                  ))}
                </ul>
              </label>
            ))}
          </div>
        </fieldset>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">Nome completo</span>
              <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" autoComplete="name" maxLength={200} />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">Celular</span>
              <input type="tel" value={phone} onChange={(e) => setPhone(formatPhone(e.target.value))} placeholder="(11) 99999-9999" className="w-full rounded-lg border border-slate-300 px-3 py-2" autoComplete="tel" inputMode="numeric" />
            </label>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">
                {planSlug === "contador" ? "CNPJ do escritório" : "CNPJ da empresa"}
              </span>
              <input type="text" value={cnpj} onChange={(e) => setCnpj(formatCnpj(e.target.value))} placeholder="00.000.000/0000-00" className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono" inputMode="text" />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">Email corporativo</span>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" autoComplete="email" />
            </label>
          </div>

          {planSlug === "contador" && (
            <p className="text-xs text-amber-700">
              Informe o CNPJ do seu escritório, não de um cliente. CNPJs de clientes serão adicionados após o cadastro.
            </p>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">Senha (min. 8 caracteres)</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" autoComplete="new-password" minLength={8} />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">Confirmar senha</span>
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" autoComplete="new-password" />
            </label>
          </div>

          {/* Billing type (for paid plans) */}
          {isPaidPlan && (
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-slate-700">Forma de pagamento</legend>
              <div className="grid grid-cols-2 gap-2">
                <label
                  className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-sm transition ${
                    billingType === "PIX"
                      ? "border-tribultz-500 bg-tribultz-50 text-tribultz-700"
                      : "border-slate-200 text-slate-600 hover:border-slate-300"
                  }`}
                >
                  <input type="radio" name="billing_type" value="PIX" checked={billingType === "PIX"} onChange={() => setBillingType("PIX")} className="sr-only" />
                  <span className="font-semibold">PIX</span>
                  <span className="text-xs text-slate-400">QR Code</span>
                </label>
                <label
                  className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-sm transition ${
                    billingType === "CREDIT_CARD"
                      ? "border-tribultz-500 bg-tribultz-50 text-tribultz-700"
                      : "border-slate-200 text-slate-600 hover:border-slate-300"
                  }`}
                >
                  <input type="radio" name="billing_type" value="CREDIT_CARD" checked={billingType === "CREDIT_CARD"} onChange={() => setBillingType("CREDIT_CARD")} className="sr-only" />
                  <span className="font-semibold">Cartão de Crédito</span>
                </label>
              </div>
            </fieldset>
          )}

          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Código de Referência (opcional)</span>
            <input
              type="text"
              value={partnerCode}
              onChange={(e) => setPartnerCode(e.target.value.toUpperCase())}
              placeholder="Ex.: KATIA"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono uppercase placeholder:font-sans placeholder:normal-case"
              maxLength={32}
            />
            <span className="mt-1 block text-xs text-slate-400">
              Foi indicado por um parceiro Tribultz? Informe o código que ele compartilhou com você.
            </span>
          </label>

          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={lgpdConsent} onChange={(e) => setLgpdConsent(e.target.checked)} className="mt-1 h-4 w-4 rounded border-slate-300" />
            <span className="text-slate-600">
              Li e concordo com a{" "}
              <Link href="/privacy" target="_blank" className="font-medium text-tribultz-700 underline">Política de Privacidade</Link>{" "}
              e autorizo o tratamento dos meus dados pessoais e financeiros conforme a LGPD (Lei 13.709/2018).
            </span>
          </label>

          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={termsAccepted} onChange={(e) => setTermsAccepted(e.target.checked)} className="mt-1 h-4 w-4 rounded border-slate-300" />
            <span className="text-slate-600">
              Li e concordo com os{" "}
              <Link href="/terms" target="_blank" className="font-medium text-tribultz-700 underline">Termos de Uso</Link>{" "}
              da Tribultz.
            </span>
          </label>

          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={refundPolicyAccepted} onChange={(e) => setRefundPolicyAccepted(e.target.checked)} className="mt-1 h-4 w-4 rounded border-slate-300" />
            <span className="text-slate-600">
              Li e concordo com a{" "}
              <Link href="/refund-policy" target="_blank" className="font-medium text-tribultz-700 underline">Política de Reembolso</Link>{" "}
              (direito de arrependimento de 7 dias, CDC art. 49).
            </span>
          </label>

          {(planSlug === "empresarial" || planSlug === "contador") && (
            <label className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
              <input type="checkbox" checked={multiTenantConsent} onChange={(e) => setMultiTenantConsent(e.target.checked)} className="mt-1 h-4 w-4 rounded border-slate-300" />
              <span className="text-amber-900">
                <strong>Responsabilidade Multi-Tenant:</strong> Declaro estar ciente de que terei
                acesso aos dados fiscais de múltiplos CNPJs (tenants) dentro da plataforma.
                Comprometo-me a operar sempre no tenant correto, evitando contaminação cruzada
                de dados entre CNPJ&apos;s.
              </span>
            </label>
          )}

          {captchaConfigured ? (
            <Turnstile
              ref={turnstileRef}
              siteKey={TURNSTILE_SITE_KEY as string}
              onSuccess={setCaptchaToken}
              onExpire={() => setCaptchaToken("")}
              options={{ theme: "light", size: "flexible" }}
            />
          ) : (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
              CAPTCHA de produção não configurado. Defina `NEXT_PUBLIC_TURNSTILE_SITE_KEY` no ambiente do frontend.
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !captchaToken || !captchaConfigured}
            className="w-full rounded-lg bg-tribultz-600 px-4 py-2.5 font-semibold text-white hover:bg-tribultz-700 disabled:opacity-70"
          >
            {loading ? "Registrando..." : isPaidPlan ? "Criar conta e pagar" : "Quero meu trial"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-slate-500">
          Já tem conta?{" "}
          <Link href="/login" className="font-medium text-tribultz-700 hover:underline">Entrar</Link>
        </p>
      </section>
      {toast ? <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </main>
  );
}
