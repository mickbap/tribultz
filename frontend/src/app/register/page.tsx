"use client";

import Link from "next/link";
import { FormEvent, useRef, useState } from "react";
import { Turnstile, type TurnstileInstance } from "@marsidev/react-turnstile";
import { Toast } from "@/components/common/Toast";
import { registerWithApi } from "@/lib/api";
import { DEFAULT_TENANT } from "@/lib/storage";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "1x00000000000000000000AA";

function formatCnpj(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 14);
  if (digits.length <= 2) return digits;
  if (digits.length <= 5) return `${digits.slice(0, 2)}.${digits.slice(2)}`;
  if (digits.length <= 8) return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5)}`;
  if (digits.length <= 12) return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8)}`;
  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12)}`;
}

function cnpjDigits(formatted: string): string {
  return formatted.replace(/\D/g, "");
}

export default function RegisterPage() {
  const [accountType, setAccountType] = useState<"empresa" | "contador">("empresa");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [cnpj, setCnpj] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [lgpdConsent, setLgpdConsent] = useState(false);
  const [multiTenantConsent, setMultiTenantConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [registered, setRegistered] = useState(false);
  const [toast, setToast] = useState<{ tone: "success" | "error"; msg: string } | null>(null);
  const [captchaToken, setCaptchaToken] = useState("");
  const turnstileRef = useRef<TurnstileInstance>(null);

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setToast(null);

    if (!fullName.trim() || !email.trim() || !password.trim()) {
      setToast({ tone: "error", msg: "Preencha todos os campos obrigatorios." });
      return;
    }
    const digits = cnpjDigits(cnpj);
    if (digits.length !== 14) {
      setToast({ tone: "error", msg: "CNPJ deve ter 14 digitos." });
      return;
    }
    if (password !== confirmPassword) {
      setToast({ tone: "error", msg: "Senhas nao conferem." });
      return;
    }
    if (password.length < 8) {
      setToast({ tone: "error", msg: "Senha deve ter no minimo 8 caracteres." });
      return;
    }
    if (!lgpdConsent) {
      setToast({ tone: "error", msg: "Voce deve aceitar a Politica de Privacidade para prosseguir." });
      return;
    }
    if (accountType === "contador" && !multiTenantConsent) {
      setToast({ tone: "error", msg: "Voce deve aceitar o termo de Responsabilidade Multi-Tenant para prosseguir." });
      return;
    }
    if (!captchaToken) {
      setToast({ tone: "error", msg: "Aguarde a verificacao de seguranca (CAPTCHA)." });
      return;
    }

    setLoading(true);
    try {
      await registerWithApi({
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        cnpj: digits,
        account_type: accountType,
        lgpd_consent: true,
        tenant_slug: DEFAULT_TENANT,
        captcha_token: captchaToken,
      });

      setRegistered(true);
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
            Enviamos um link de confirmacao para <strong>{email}</strong>.
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

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-2xl">
        <h1 className="text-2xl font-bold text-slate-900">Criar conta</h1>
        <p className="mt-1 text-sm text-slate-500">Cadastre-se para acessar o Tribultz Console.</p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium text-slate-700">Tipo de conta</legend>
            <div className="grid grid-cols-2 gap-2">
              <label
                className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-sm transition ${
                  accountType === "empresa"
                    ? "border-tribultz-500 bg-tribultz-50 text-tribultz-700"
                    : "border-slate-200 text-slate-600 hover:border-slate-300"
                }`}
              >
                <input
                  type="radio"
                  name="account_type"
                  value="empresa"
                  checked={accountType === "empresa"}
                  onChange={() => setAccountType("empresa")}
                  className="sr-only"
                />
                <span className="font-semibold">Empresa</span>
                <span className="text-xs text-slate-400">1 CNPJ</span>
              </label>
              <label
                className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-sm transition ${
                  accountType === "contador"
                    ? "border-tribultz-500 bg-tribultz-50 text-tribultz-700"
                    : "border-slate-200 text-slate-600 hover:border-slate-300"
                }`}
              >
                <input
                  type="radio"
                  name="account_type"
                  value="contador"
                  checked={accountType === "contador"}
                  onChange={() => setAccountType("contador")}
                  className="sr-only"
                />
                <span className="font-semibold">Contador</span>
                <span className="text-xs text-slate-400">Multi-CNPJ</span>
              </label>
            </div>
            <p className="text-xs text-slate-400">
              {accountType === "empresa"
                ? "Sua empresa tera acesso exclusivo ao seu CNPJ."
                : "Voce podera gerenciar multiplos CNPJs de clientes."}
            </p>
          </fieldset>

          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Nome completo</span>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              autoComplete="name"
              maxLength={200}
            />
          </label>

          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">
              {accountType === "contador"
                ? "CNPJ do escritorio contabil"
                : "CNPJ da empresa"}
            </span>
            <input
              type="text"
              value={cnpj}
              onChange={(e) => setCnpj(formatCnpj(e.target.value))}
              placeholder="00.000.000/0000-00"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono"
              inputMode="numeric"
            />
            {accountType === "contador" && (
              <span className="mt-1 block text-xs text-amber-700">
                Informe o CNPJ do seu escritorio, nao de um cliente. CNPJs de clientes serao adicionados apos o cadastro.
              </span>
            )}
          </label>

          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Email corporativo</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              autoComplete="email"
            />
          </label>

          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Senha (min. 8 caracteres)</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              autoComplete="new-password"
              minLength={8}
            />
          </label>

          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Confirmar senha</span>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              autoComplete="new-password"
            />
          </label>

          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={lgpdConsent}
              onChange={(e) => setLgpdConsent(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-slate-300"
            />
            <span className="text-slate-600">
              Li e concordo com a{" "}
              <Link href="/privacy" target="_blank" className="font-medium text-tribultz-700 underline">
                Politica de Privacidade
              </Link>{" "}
              e autorizo o tratamento dos meus dados pessoais e financeiros conforme a LGPD
              (Lei 13.709/2018). Estou ciente de que o Tribultz atuara como custodiante dos
              dados fiscais enviados.
            </span>
          </label>

          {accountType === "contador" && (
            <label className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
              <input
                type="checkbox"
                checked={multiTenantConsent}
                onChange={(e) => setMultiTenantConsent(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-slate-300"
              />
              <span className="text-amber-900">
                <strong>Responsabilidade Multi-Tenant:</strong> Declaro estar ciente de que, como
                contador, terei acesso aos dados fiscais de multiplos CNPJs (tenants) dentro da
                plataforma. Comprometo-me a operar sempre no tenant correto, evitando
                contaminacao cruzada de dados entre clientes. Reconheco que processar dados no
                tenant errado pode gerar inconsistencias fiscais graves. Comprometo-me com a
                confidencialidade dos dados de cada cliente conforme a LGPD (Art. 46) e o Codigo
                de Etica do CFC.
              </span>
            </label>
          )}

          <Turnstile
            ref={turnstileRef}
            siteKey={TURNSTILE_SITE_KEY}
            onSuccess={setCaptchaToken}
            onExpire={() => setCaptchaToken("")}
            options={{ theme: "light", size: "flexible" }}
          />

          <button
            type="submit"
            disabled={loading || !captchaToken}
            className="w-full rounded-lg bg-tribultz-600 px-4 py-2.5 font-semibold text-white hover:bg-tribultz-700 disabled:opacity-70"
          >
            {loading ? "Registrando..." : "Criar conta"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-slate-500">
          Ja tem conta?{" "}
          <Link href="/login" className="font-medium text-tribultz-700 hover:underline">
            Entrar
          </Link>
        </p>
      </section>
      {toast ? <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </main>
  );
}
