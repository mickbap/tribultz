"use client";

import { type ReactNode } from "react";
import { isPlanAtLeast, type PlanSlug } from "@/lib/plan";

type Props = {
  /** Minimum plan required to access this content. */
  requiredPlan: PlanSlug;
  /** Message to display when plan is insufficient. */
  message?: string;
  /** Content to render when access is granted. */
  children: ReactNode;
};

/**
 * Wrapper that shows an upgrade CTA if the user's plan is below the required level.
 *
 * Usage:
 *   <UpgradeGate requiredPlan="profissional" message="Relatório PDF disponível nos planos Profissional e Contador.">
 *     <PdfButton />
 *   </UpgradeGate>
 */
export default function UpgradeGate({ requiredPlan, message, children }: Props) {
  if (isPlanAtLeast(requiredPlan)) {
    return <>{children}</>;
  }

  const defaultMessage = `Recurso disponível a partir do plano ${requiredPlan.charAt(0).toUpperCase() + requiredPlan.slice(1)}.`;

  return (
    <div className="rounded-lg border border-yellow-300 bg-yellow-50 p-4 text-center">
      <p className="text-sm text-yellow-800">{message ?? defaultMessage}</p>
      <a
        href="/billing"
        className="mt-2 inline-block rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
      >
        Fazer upgrade
      </a>
    </div>
  );
}
