"use client";

import Link from "next/link";
import { useState } from "react";
import { Evidence } from "@/lib/types";

function iconFor(type: Evidence["type"]): string {
  switch (type) {
    case "job":
      return "JB";
    case "audit":
      return "AU";
    case "xml":
      return "XML";
    case "print":
      return "PR";
    case "file":
      return "AR";
    case "link":
      return "LK";
    default:
      return "EV";
  }
}

function hrefFor(item: Evidence): string | null {
  if (item.type === "job" && item.job_id) return `/jobs/${item.job_id}`;
  if (item.type === "audit") {
    if (item.audit_id) return `/audit?audit_id=${encodeURIComponent(item.audit_id)}`;
    if (item.job_id) return `/audit?job_id=${encodeURIComponent(item.job_id)}`;
  }
  if (item.href) return item.href;
  return null;
}

export function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  if (!evidence.length) return null;

  return (
    <ul className="mt-3 space-y-2" aria-label="Evidências">
      {evidence.map((item, idx) => {
        const href = hrefFor(item);
        const key = `${item.id ?? item.label}-${idx}`;

        return (
          <li key={key} className="rounded-lg border border-slate-200 bg-white p-2 text-sm text-slate-700">
            <div className="flex flex-wrap items-center gap-2">
              <span
                aria-hidden
                className="inline-grid h-5 w-7 place-items-center rounded-full bg-slate-100 px-1 text-[10px] font-semibold text-slate-600"
              >
                {iconFor(item.type)}
              </span>
              <span className="font-medium">{item.label}</span>
              {item.id ? <span className="font-mono text-xs text-slate-500">[{item.id}]</span> : null}
              {href ? (
                <Link href={href} className="text-tribultz-700 hover:underline">
                  Abrir
                </Link>
              ) : null}
            </div>

            {item.xpath ? <p className="mt-1 text-xs text-slate-500">XPath: {item.xpath}</p> : null}
            {item.snippet ? (
              <div className="mt-1">
                <pre className="scroll-thin max-h-20 overflow-auto rounded bg-slate-100 p-2 text-[11px]">{item.snippet}</pre>
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard
                      .writeText(item.snippet ?? "")
                      .then(() => {
                        setCopiedId(key);
                        window.setTimeout(() => setCopiedId((curr) => (curr === key ? null : curr)), 1200);
                      })
                      .catch(() => {
                        setCopiedId(null);
                      });
                  }}
                  className="mt-1 rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100"
                >
                  {copiedId === key ? "Copiado" : "Copiar snippet"}
                </button>
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
