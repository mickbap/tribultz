"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { Toast } from "@/components/common/Toast";
import { forgotPassword } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [toast, setToast] = useState<{ tone: "success" | "error"; msg: string } | null>(null);

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setToast(null);

    if (!email.trim()) {
      setToast({ tone: "error", msg: "Informe seu email." });
      return;
    }

    setLoading(true);
    try {
      await forgotPassword(email.trim());
      setSent(true);
    } catch (err) {
      setToast({
        tone: "error",
        msg: err instanceof Error ? err.message : "Falha ao solicitar redefinicao.",
      });
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
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
            Se o email <strong>{email}</strong> estiver cadastrado, voce recebera um link para redefinir sua senha.
          </p>
          <p className="mt-2 text-sm text-slate-500">
            O link expira em 1 hora.
          </p>
          <Link
            href="/login"
            className="mt-6 inline-block rounded-lg bg-tribultz-600 px-6 py-2.5 font-semibold text-white hover:bg-tribultz-700"
          >
            Voltar ao login
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-2xl">
        <h1 className="text-2xl font-bold text-slate-900">Esqueci minha senha</h1>
        <p className="mt-1 text-sm text-slate-500">
          Informe seu email e enviaremos um link para redefinir sua senha.
        </p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              autoComplete="email"
              autoFocus
            />
          </label>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-tribultz-600 px-4 py-2.5 font-semibold text-white hover:bg-tribultz-700 disabled:opacity-70"
          >
            {loading ? "Enviando..." : "Enviar link de redefinicao"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-slate-500">
          Lembrou a senha?{" "}
          <Link href="/login" className="font-medium text-tribultz-700 hover:underline">
            Voltar ao login
          </Link>
        </p>
      </section>
      {toast ? <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </main>
  );
}
