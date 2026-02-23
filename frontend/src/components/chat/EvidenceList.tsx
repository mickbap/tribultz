"use client";

import Link from "next/link";
import { Evidence } from "@/lib/types";

function iconFor(type: Evidence["type"]): string {
  switch (type) {
    case "job":
      return "JB";
    case "audit":
      return "AU";
    case "file":
      return "AR";
    case "link":
      return "LK";
    default:
      return "EV";
  }
}

function hrefFor(item: Evidence): string {
  if (item.type === "job" && item.job_id) return `/jobs/${item.job_id}`;
  if (item.type === "audit") {
    if (item.audit_id) return `/audit?audit_id=${encodeURIComponent(item.audit_id)}`;
    if (item.job_id) return `/audit?job_id=${encodeURIComponent(item.job_id)}`;
  }
  return item.href || "#";
}

export function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  if (!evidence.length) return null;
  return (
    <ul className="mt-3 flex flex-wrap gap-2" aria-label="Evidências">
      {evidence.map((item, idx) => (
        <li key={`${item.type}-${item.href}-${idx}`}>
          <Link
            href={hrefFor(item)}
            className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white px-3 py-1 text-sm text-slate-700 hover:border-tribultz-400 hover:text-tribultz-700"
          >
            <span
              aria-hidden
              className="inline-grid h-5 w-5 place-items-center rounded-full bg-slate-100 text-[10px] font-semibold text-slate-600"
            >
              {iconFor(item.type)}
            </span>
            <span>{item.label}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
