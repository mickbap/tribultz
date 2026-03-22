"use client";

import { FormEvent, useState } from "react";
import { Toast } from "@/components/common/Toast";
import { apiFetch } from "@/lib/api";
import { getMockMode } from "@/lib/storage";

type FeedbackCategory = "bug" | "sugestao" | "elogio";

const CATEGORY_LABELS: Record<FeedbackCategory, string> = {
  bug: "Bug / Problema",
  sugestao: "Sugestao de melhoria",
  elogio: "Elogio",
};

export default function FeedbackPage() {
  const [category, setCategory] = useState<FeedbackCategory>("sugestao");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ tone: "success" | "error" | "info"; msg: string } | null>(null);

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setToast(null);

    if (message.trim().length < 10) {
      setToast({ tone: "error", msg: "Mensagem deve ter no minimo 10 caracteres." });
      return;
    }

    if (getMockMode()) {
      setToast({ tone: "success", msg: "Feedback registrado (modo demo). Obrigado!" });
      setMessage("");
      return;
    }

    setLoading(true);
    try {
      await apiFetch("/api/v1/feedback/", {
        method: "POST",
        body: JSON.stringify({ category, message: message.trim() }),
      });
      setToast({ tone: "success", msg: "Feedback enviado com sucesso. Obrigado!" });
      setMessage("");
    } catch (err) {
      setToast({
        tone: "error",
        msg: err instanceof Error ? err.message : "Falha ao enviar feedback.",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Feedback</h1>
        <p className="text-sm text-slate-500">
          Sua opiniao e importante para melhorar o Tribultz. Envie sugestoes, reporte bugs ou deixe um elogio.
        </p>
      </header>

      <form onSubmit={onSubmit} className="max-w-lg space-y-4 rounded-2xl border border-slate-200 bg-white p-6">
        <label className="block text-sm">
          <span className="mb-1 block text-slate-600">Categoria</span>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as FeedbackCategory)}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
          >
            {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm">
          <span className="mb-1 block text-slate-600">Mensagem (min. 10 caracteres)</span>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Descreva sua experiencia, sugestao ou problema..."
            className="min-h-32 w-full rounded-lg border border-slate-300 p-3 text-sm"
            maxLength={2000}
          />
          <span className="text-xs text-slate-400">{message.length}/2000</span>
        </label>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-tribultz-600 px-4 py-2.5 font-semibold text-white hover:bg-tribultz-700 disabled:opacity-70"
        >
          {loading ? "Enviando..." : "Enviar feedback"}
        </button>
      </form>

      {toast ? <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}
