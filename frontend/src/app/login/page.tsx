"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Toast } from "@/components/common/Toast";
import { loginWithApi, resendVerificationEmail } from "@/lib/api";
import { DEFAULT_TENANT, setAccountType, setMockMode, setTenantId, setTenants, setToken } from "@/lib/storage";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loadingApi, setLoadingApi] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emailUnverified, setEmailUnverified] = useState(false);
  const [resending, setResending] = useState(false);

  function enterDemo(): void {
    setMockMode(true);
    setTenantId(DEFAULT_TENANT);
    setToken("demo-token");
    window.dispatchEvent(new Event("tribultz-settings-updated"));
    router.push("/dashboard");
  }

  async function enterApi(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError("Informe email e senha para entrar em API Mode.");
      return;
    }

    setLoadingApi(true);
    setError(null);
    try {
      const login = await loginWithApi({
        email: email.trim(),
        password,
        tenant_slug: DEFAULT_TENANT,
      });
      if (!login.access_token) {
        throw new Error("Resposta de login sem access_token.");
      }
      setMockMode(false);
      setTenantId(login.tenant_id ?? DEFAULT_TENANT);
      setToken(login.access_token);
      setAccountType(login.account_type ?? "empresa");
      setTenants(login.tenants ?? []);
      window.dispatchEvent(new Event("tribultz-settings-updated"));
      router.push("/dashboard");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Falha ao autenticar em API Mode.";
      if (msg.includes("nao verificado") || msg.includes("not verified")) {
        setEmailUnverified(true);
      }
      setError(msg);
    } finally {
      setLoadingApi(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <section className="w-full max-w-4xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="grid min-h-[620px] md:grid-cols-[1.1fr_1fr]">
          <div className="bg-gradient-to-br from-tribultz-900 via-tribultz-700 to-tribultz-500 p-10 text-white">
            <p className="mb-2 text-xs uppercase tracking-[0.2em] text-blue-100">TRIBULTZ Console v0.2.0</p>
            <h1 className="mb-4 text-4xl font-bold leading-tight">Conformidade tributaria em tempo de execucao.</h1>
            <p className="max-w-md text-blue-50">Emita certo. Credite certo. Concilie sempre.</p>
          </div>

          <div className="flex items-center p-8 md:p-10">
            <div className="w-full">
              <h2 className="text-2xl font-semibold text-slate-900">Entrar no Console</h2>
              <p className="mt-1 text-sm text-slate-500">Escolha entre Demo (mock) ou autenticacao real de API.</p>

              <div className="mt-8 space-y-4">
                <button
                  type="button"
                  onClick={enterDemo}
                  className="w-full rounded-lg bg-tribultz-600 px-4 py-2.5 font-semibold text-white hover:bg-tribultz-700"
                >
                  Entrar (Demo)
                </button>
                <p className="text-xs text-slate-500">Mock Mode fica ON por padrao e roda sem backend.</p>

                <form className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-3" onSubmit={enterApi}>
                  <p className="text-sm font-semibold text-slate-700">Entrar (API)</p>
                  <label className="block text-xs text-slate-600" htmlFor="login-email">
                    Email
                  </label>
                  <input
                    id="login-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    autoComplete="email"
                  />
                  <label className="block text-xs text-slate-600" htmlFor="login-password">
                    Senha
                  </label>
                  <input
                    id="login-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    autoComplete="current-password"
                  />
                  <button
                    type="submit"
                    disabled={loadingApi}
                    className="w-full rounded-lg border border-tribultz-400 bg-white px-4 py-2 text-sm font-semibold text-tribultz-700 hover:bg-tribultz-50 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {loadingApi ? "Autenticando..." : "Entrar (API)"}
                  </button>
                  {emailUnverified && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                      <p className="text-xs text-amber-800">
                        Email nao verificado. Verifique sua caixa de entrada.
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
                              tenant_slug: DEFAULT_TENANT,
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
                        {resending ? "Reenviando..." : "Reenviar email de verificacao"}
                      </button>
                    </div>
                  )}
                </form>
              </div>
            </div>
          </div>
        </div>
      </section>
      <p className="mt-4 text-center text-sm text-slate-500">
        Nao tem conta?{" "}
        <a href="/register" className="font-medium text-tribultz-700 hover:underline">
          Criar conta
        </a>
      </p>
      {error ? <Toast message={error} tone="error" onClose={() => setError(null)} /> : null}
    </main>
  );
}
