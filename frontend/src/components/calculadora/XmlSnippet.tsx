"use client";

import { useState } from "react";

type XmlSnippetProps = {
  xml: string;
};

export function XmlSnippet({ xml }: XmlSnippetProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(xml);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback silencioso
    }
  }

  return (
    <div className="relative rounded-lg border border-slate-200 bg-slate-50">
      <button
        type="button"
        onClick={handleCopy}
        className="absolute right-2 top-2 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-100"
      >
        {copied ? "Copiado!" : "Copiar"}
      </button>
      <pre className="overflow-x-auto p-4 pr-20 font-mono text-xs leading-relaxed text-slate-700">
        {xml}
      </pre>
    </div>
  );
}
