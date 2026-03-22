"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Toast } from "@/components/common/Toast";
import { registerWithApi, loginWithApi } from "@/lib/api";
import { setMockMode, setTenantId, setToken } from "@/lib/storage";

export default function RegisterPage() {
  const router = useRouter();
  const [tenant, setTenant] = useState("tenant-a");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ tone: "success" | "error"; msg: string } | null>(null);

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setToast(null);

    if (!fullName.trim() || !email.trim() || !password.trim()) {
      setToast({ tone: "error", msg: "Preencha todos os campos." });
      return;
    }
    if (password !== confirmPassword) {
      setToast({ tone: "error", msg: "Senhas nao conferem." });
      return;
    }
    if (password.length < 6) {
      setToast({ tone: "error", msg: "Senha deve ter no minimo 6 caracteres." });
      return;
    }

    setLoading(true);
    try {
      await registerWithApi({
        email: email.trim(),
        password,
        full_name: fullName.trim(),
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
            />
          </label>

          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              autoComplete="email"
            />
          </label>

          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Senha</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              autoComplete="new-password"
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
