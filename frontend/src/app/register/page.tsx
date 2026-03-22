"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Toast } from "@/components/common/Toast";
import { registerWithApi, loginWithApi } from "@/lib/api";
import { setMockMode, setTenantId, setToken } from "@/lib/storage";

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
  const router = useRouter();
  const [tenant, setTenant] = useState("tenant-a");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [cnpj, setCnpj] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [lgpdConsent, setLgpdConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ tone: "success" | "error"; msg: string } | null>(null);

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

    setLoading(true);
    try {
      await registerWithApi({
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        cnpj: digits,
        lgpd_consent: true,
        tenant_slug: tenant,
      });

      // Auto-login after registration
      const login = await loginWithApi({
        email: email.trim(),
        password,
        tenant_slug: tenant,
      });

      setMockMode(false);
      setTenantId(tenant);
      setToken(login.access_token);
      window.dispatchEvent(new Event("tribultz-settings-updated"));
      router.push("/dashboard");
    } catch (err) {
      setToast({
        tone: "error",
        msg: err instanceof Error ? err.message : "Falha ao registrar.",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-2xl">
        <h1 className="text-2xl font-bold text-slate-900">Criar conta</h1>
        <p className="mt-1 text-sm text-slate-500">Cadastre-se para acessar o Tribultz Console.</p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Tenant</span>
            <select
              value={tenant}
              onChange={(e) => setTenant(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
            >
              <option value="tenant-a">tenant-a</option>
              <option value="tenant-b">tenant-b</option>
              <option value="tenant-prod">tenant-prod</option>
            </select>
          </label>

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
            <span className="mb-1 block text-slate-600">CNPJ</span>
            <input
              type="text"
              value={cnpj}
              onChange={(e) => setCnpj(formatCnpj(e.target.value))}
              placeholder="00.000.000/0000-00"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono"
              inputMode="numeric"
            />
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

          <button
            type="submit"
            disabled={loading}
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
