"use client";

import { FormEvent, Suspense, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Turnstile, type TurnstileInstance } from "@marsidev/react-turnstile";
import { Toast } from "@/components/common/Toast";
import { loginWithApi, resendVerificationEmail } from "@/lib/api";
import { setAccountType, setTenantId, setTenants, setToken } from "@/lib/storage";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-tribultz-600" />
      </div>
    }>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loadingApi, setLoadingApi] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emailUnverified, setEmailUnverified] = useState(false);
  const [resending, setResending] = useState(false);
  const [captchaToken, setCaptchaToken] = useState("");
  const turnstileRef = useRef<TurnstileInstance>(null);
  const captchaConfigured = Boolean(TURNSTILE_SITE_KEY?.trim());

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError("Informe email e senha para entrar.");
      return;
    }

    if (!captchaConfigured) {
      setError("CAPTCHA indisponível no momento. Contate o suporte.");
      return;
    }

    if (!captchaToken) {
      setError("Aguarde a verificação de segurança (CAPTCHA).");
      return;
    }

    setLoadingApi(true);
    setError(null);
    try {
      const login = await loginWithApi({
        email: email.trim(),
        password,
        tenant_slug: "",
        captcha_token: captchaToken,
      });
      if (!login.access_token) {
        throw new Error("Resposta de login sem access_token.");
      }
      setTenantId(login.tenant_id ?? "");
      setToken(login.access_token);
      setAccountType(login.account_type ?? "empresa");
      setTenants(login.tenants ?? []);
      window.dispatchEvent(new Event("tribultz-settings-updated"));
      // Superadmins go to plan/mode selector before entering the app
      if (login.role === "superadmin") {
        router.push("/select-mode");
      } else {
        router.push(redirectTo ?? "/dashboard");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Falha ao autenticar.";
      if (msg.includes("não verificado") || msg.includes("not verified")) {
        setEmailUnverified(true);
      }
      setError(msg);
      setCaptchaToken("");
      turnstileRef.current?.reset();
    } finally {
      setLoadingApi(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <section className="w-full max-w-4xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="grid min-h-[620px] md:grid-cols-[1.1fr_1fr]">
          <div className="bg-gradient-to-br from-tribultz-900 via-tribultz-700 to-tribultz-500 p-10 text-white">
            <p className="mb-2 text-xs uppercase tracking-[0.2em] text-blue-100">TRIBULTZ</p>
            <h1 className="mb-4 text-4xl font-bold leading-tight">Conformidade tributária em tempo de execução.</h1>
            <p className="max-w-md text-blue-50">Emita certo. Credite certo. Concilie sempre.</p>
          </div>

          <div className="flex items-center p-8 md:p-10">
            <div className="w-full">
              <h2 className="text-2xl font-semibold text-slate-900">Entrar</h2>
              <p className="mt-1 text-sm text-slate-500">Acesse sua conta para gerenciar sua conformidade tributária.</p>

              <form className="mt-8 space-y-4" onSubmit={onSubmit}>
                <label className="block text-sm" htmlFor="login-email">
                  <span className="mb-1 block text-slate-600">Email</span>
                  <input
                    id="login-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    autoComplete="email"
                    autoFocus
                  />
                </label>
                <label className="block text-sm" htmlFor="login-password">
                  <span className="mb-1 block text-slate-600">Senha</span>
                  <input
                    id="login-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    autoComplete="current-password"
                  />
                </label>
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
                  disabled={loadingApi || !captchaToken || !captchaConfigured}
                  className="w-full rounded-lg bg-tribultz-600 px-4 py-2.5 font-semibold text-white hover:bg-tribultz-700 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {loadingApi ? "Autenticando..." : "Entrar"}
                </button>
                {emailUnverified && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                    <p className="text-xs text-amber-800">
                      Email não verificado. Verifique sua caixa de entrada.
                    </p>
                    <button
                      type="button"
                      disabled={resending}
                      onClick={async () => {
                        setResending(true);
                        try {
                          await resendVerificationEmail({
                            email: email.trim(),
                            password: password,
                            tenant_slug: "",
                          });
                          setError(null);
                          setEmailUnverified(false);
                          setError("Novo link enviado! Verifique sua caixa de entrada.");
                        } catch {
                          setError("Falha ao reenviar. Tente novamente.");
                        } finally {
                          setResending(false);
                        }
                      }}
                      className="mt-2 text-xs font-semibold text-amber-700 underline hover:text-amber-900 disabled:opacity-50"
                    >
                      {resending ? "Reenviando..." : "Reenviar email de verificação"}
                    </button>
                  </div>
                )}
                <p className="text-center text-xs text-slate-500">
                  <Link href="/forgot-password" className="font-medium text-tribultz-700 hover:underline">
                    Esqueci minha senha
                  </Link>
                </p>
              </form>
            </div>
          </div>
        </div>
      </section>
      <p className="mt-4 text-center text-sm text-slate-500">
        Não tem conta?{" "}
        <Link href="/register" className="font-medium text-tribultz-700 hover:underline">
          Criar conta
        </Link>
        {" "}&middot;{" "}
        <Link href="/changelog" className="font-medium text-slate-500 hover:text-tribultz-700 hover:underline">
          Novidades
        </Link>
      </p>
      {error ? <Toast message={error} tone="error" onClose={() => setError(null)} /> : null}
    </main>
  );
}
