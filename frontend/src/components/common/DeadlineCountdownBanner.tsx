"use client";

import Link from "next/link";
import { daysUntilDeadline } from "@/lib/deadlineCountdown";

/**
 * Countdown banner for the 03/08/2026 SEFAZ production deadline (Regime Normal/CRT 3,
 * Rejeições 1115/1119 — NT 2025.002 v1.40, #403). Self-expiring: renders null once the
 * deadline has passed, so no manual flag needs to be flipped after the date (#407).
 */
export default function DeadlineCountdownBanner() {
  const days = daysUntilDeadline();
  if (days <= 0) return null;

  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm text-amber-900">
      <span className="font-semibold">
        {days} dia{days !== 1 ? "s" : ""} até 03/08/2026
      </span>{" "}
      — a SEFAZ passa a rejeitar NF-e do Regime Normal (CRT 3) sem IBS/CBS no item
      (Rejeição 1115) ou sem o grupo de totais IBSCBSTot (Rejeição 1119). Valide antes
      que a SEFAZ rejeite.{" "}
      <Link
        href="/blog/nfe-rejeitada-03-08-2026-regime-normal-crt3"
        className="font-medium underline hover:text-amber-950"
      >
        Entenda o prazo
      </Link>
    </div>
  );
}
