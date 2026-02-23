"use client";

type ToastProps = {
  message: string;
  tone?: "error" | "info" | "success";
  onClose?: () => void;
};

const tones = {
  error: "border-rose-300 bg-rose-50 text-rose-800",
  info: "border-slate-300 bg-white text-slate-700",
  success: "border-emerald-300 bg-emerald-50 text-emerald-800",
};

export function Toast({ message, tone = "info", onClose }: ToastProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-4 right-4 z-50 max-w-md rounded-xl border px-4 py-3 shadow-lg ${tones[tone]}`}
    >
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm">{message}</p>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="rounded px-2 py-0.5 text-xs hover:bg-black/5"
            aria-label="Fechar aviso"
          >
            Fechar
          </button>
        ) : null}
      </div>
    </div>
  );
}
