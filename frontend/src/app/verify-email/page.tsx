"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type VerifyState = "loading" | "verified" | "already_verified" | "error";

function VerifyEmailContent() {
  const params = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<VerifyState>("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setErrorMsg("Token de verificação ausente.");
      return;
    }

    fetch(`${API_BASE}/api/v1/auth/verify-email?token=${encodeURIComponent(token)}`)
      .then(async (res) => {
        const data = await res.json();
        if (res.ok) {
          setState(data.status === "already_verified" ? "already_verified" : "verified");
        } else {
          setState("error");
          setErrorMsg(data.detail ?? "Falha na verificação.");
        }
      })
      .catch(() => {
        setState("error");
        setErrorMsg("Erro de conexão. Tente novamente.");
      });
  }, [token]);

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-2xl">
        {state === "loading" && (
          <>
            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-tribultz-200 border-t-tribultz-600" />
            <h1 className="text-xl font-bold text-slate-900">Verificando email...</h1>
            <p className="mt-2 text-sm text-slate-500">Aguarde um momento.</p>
          </>
        )}

        {state === "verified" && (
          <>
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100">
              <svg className="h-7 w-7 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-slate-900">Email verificado!</h1>
            <p className="mt-2 text-sm text-slate-500">Sua conta está ativa. Você já pode fazer login.</p>
            <Link
              href="/login"
              className="mt-6 inline-block rounded-lg bg-tribultz-600 px-6 py-2.5 font-semibold text-white hover:bg-tribultz-700"
            >
              Ir para login
            </Link>
          </>
        )}

        {state === "already_verified" && (
          <>
            <h1 className="text-xl font-bold text-slate-900">Email já verificado</h1>
            <p className="mt-2 text-sm text-slate-500">Seu email já foi confirmado anteriormente.</p>
            <Link
              href="/login"
              className="mt-6 inline-block rounded-lg bg-tribultz-600 px-6 py-2.5 font-semibold text-white hover:bg-tribultz-700"
            >
              Ir para login
            </Link>
          </>
        )}

        {state === "error" && (
          <>
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-red-100">
              <svg className="h-7 w-7 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-slate-900">Falha na verificação</h1>
            <p className="mt-2 text-sm text-red-600">{errorMsg}</p>
            <p className="mt-3 text-sm text-slate-500">
              O link pode ter expirado (válido por 24h). Tente fazer login para
              solicitar um novo email de verificação.
            </p>
            <Link
              href="/login"
              className="mt-6 inline-block rounded-lg border border-slate-300 px-6 py-2.5 font-semibold text-slate-700 hover:bg-slate-100"
            >
              Ir para login
            </Link>
          </>
        )}
      </section>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <main className="grid min-h-screen place-items-center p-6">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-tribultz-200 border-t-tribultz-600" />
        </main>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
