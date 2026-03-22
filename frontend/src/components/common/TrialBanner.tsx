"use client";

import { getSubscriptionStatus, getTrialRemainingHours } from "@/lib/plan";

/**
 * Countdown banner for trial users. Shows hours remaining and upgrade CTA.
 * Rendered in AppShell for trial users only.
 */
export default function TrialBanner() {
  const status = getSubscriptionStatus();
  if (status !== "trial") return null;

  const hours = getTrialRemainingHours();
  if (hours === null) return null;

  const isExpired = hours <= 0;
  const bgColor = isExpired ? "bg-red-600" : hours <= 24 ? "bg-orange-500" : "bg-blue-600";

  return (
    <div className={`${bgColor} px-4 py-2 text-center text-sm text-white`}>
      {isExpired ? (
        <span>Seu trial expirou. </span>
      ) : (
        <span>
          Trial: {hours}h restante{hours !== 1 ? "s" : ""}.{" "}
        </span>
      )}
      <a
        href="/billing"
        className="underline font-medium hover:text-white/90"
      >
        Adquira o Starter
      </a>
    </div>
  );
}
