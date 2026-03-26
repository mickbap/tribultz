/**
 * Plan context — localStorage-backed plan/usage state + helpers.
 *
 * Usage:
 *   import { getPlanSlug, canAccess, PLAN_FEATURES } from "@/lib/plan";
 */

// ── Storage keys ────────────────────────────────────────────────

const KEY_PLAN = "tribultz.plan_slug";
const KEY_STATUS = "tribultz.subscription_status";
const KEY_TRIAL_ENDS = "tribultz.trial_ends_at";
const KEY_USAGE = "tribultz.usage";

function safeLocalStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  return window.localStorage;
}

// ── Plan feature matrix ─────────────────────────────────────────

export type PlanSlug = "trial" | "starter" | "profissional" | "empresarial" | "contador";

export type PlanFeatures = {
  name: string;
  priceCents: number;
  maxValidations: number | null; // null = unlimited
  maxAiMessages: number | null;
  hasPdfReports: boolean;
  hasBatch: boolean;
  hasDashboard: boolean;
  hasApiAccess: boolean;
  hasMultiCnpj: boolean;
  trialDays: number | null;
};

export const PLAN_FEATURES: Record<PlanSlug, PlanFeatures> = {
  trial: {
    name: "Trial",
    priceCents: 0,
    maxValidations: 5,
    maxAiMessages: 25,
    hasPdfReports: false,
    hasBatch: false,
    hasDashboard: false,
    hasApiAccess: false,
    hasMultiCnpj: false,
    trialDays: 3,
  },
  starter: {
    name: "Starter",
    priceCents: 4990,
    maxValidations: 10,
    maxAiMessages: 50,
    hasPdfReports: false,
    hasBatch: false,
    hasDashboard: true,
    hasApiAccess: false,
    hasMultiCnpj: false,
    trialDays: null,
  },
  profissional: {
    name: "Profissional",
    priceCents: 14900,
    maxValidations: 500,
    maxAiMessages: null,
    hasPdfReports: true,
    hasBatch: true,
    hasDashboard: true,
    hasApiAccess: true,
    hasMultiCnpj: false,
    trialDays: null,
  },
  empresarial: {
    name: "Empresarial",
    priceCents: 24900,
    maxValidations: 2000,
    maxAiMessages: null,
    hasPdfReports: true,
    hasBatch: true,
    hasDashboard: true,
    hasApiAccess: true,
    hasMultiCnpj: true, // filiais — até 10 CNPJs
    trialDays: null,
  },
  contador: {
    name: "Contador",
    priceCents: 34900,
    maxValidations: null,
    maxAiMessages: null,
    hasPdfReports: true,
    hasBatch: true,
    hasDashboard: true,
    hasApiAccess: true,
    hasMultiCnpj: true,
    trialDays: null,
  },
};

// ── Plan hierarchy (for upgrade comparisons) ────────────────────

const PLAN_ORDER: PlanSlug[] = ["trial", "starter", "profissional", "empresarial", "contador"];

// ── Storage getters/setters ─────────────────────────────────────

export function getPlanSlug(): PlanSlug {
  const store = safeLocalStorage();
  if (!store) return "trial";
  const raw = store.getItem(KEY_PLAN);
  if (raw && raw in PLAN_FEATURES) return raw as PlanSlug;
  return "trial";
}

export function setPlanSlug(slug: PlanSlug): void {
  const store = safeLocalStorage();
  if (!store) return;
  store.setItem(KEY_PLAN, slug);
}

export function getSubscriptionStatus(): string {
  const store = safeLocalStorage();
  if (!store) return "trial";
  return store.getItem(KEY_STATUS) ?? "trial";
}

export function setSubscriptionStatus(status: string): void {
  const store = safeLocalStorage();
  if (!store) return;
  store.setItem(KEY_STATUS, status);
}

export function getTrialEndsAt(): string | null {
  const store = safeLocalStorage();
  if (!store) return null;
  return store.getItem(KEY_TRIAL_ENDS);
}

export function setTrialEndsAt(date: string | null): void {
  const store = safeLocalStorage();
  if (!store) return;
  if (date) store.setItem(KEY_TRIAL_ENDS, date);
  else store.removeItem(KEY_TRIAL_ENDS);
}

export type UsageData = {
  validationsUsed: number;
  aiMessagesUsed: number;
  period: string;
};

export function getUsage(): UsageData {
  const store = safeLocalStorage();
  if (!store) return { validationsUsed: 0, aiMessagesUsed: 0, period: "" };
  try {
    return JSON.parse(store.getItem(KEY_USAGE) ?? "{}") as UsageData;
  } catch {
    return { validationsUsed: 0, aiMessagesUsed: 0, period: "" };
  }
}

export function setUsage(usage: UsageData): void {
  const store = safeLocalStorage();
  if (!store) return;
  store.setItem(KEY_USAGE, JSON.stringify(usage));
}

// ── Access helpers ──────────────────────────────────────────────

/**
 * Check if the current plan has a specific feature.
 */
export function canAccess(feature: keyof PlanFeatures): boolean {
  const slug = getPlanSlug();
  const plan = PLAN_FEATURES[slug];
  const val = plan[feature];
  if (typeof val === "boolean") return val;
  return val !== null && val !== 0;
}

/**
 * Check if user's plan is at least the required level.
 */
export function isPlanAtLeast(required: PlanSlug): boolean {
  const current = getPlanSlug();
  return PLAN_ORDER.indexOf(current) >= PLAN_ORDER.indexOf(required);
}

/**
 * Get trial remaining time in hours. Returns null if not on trial.
 */
export function getTrialRemainingHours(): number | null {
  const status = getSubscriptionStatus();
  if (status !== "trial") return null;
  const ends = getTrialEndsAt();
  if (!ends) return null;
  const diff = new Date(ends).getTime() - Date.now();
  if (diff <= 0) return 0;
  return Math.ceil(diff / (1000 * 60 * 60));
}

/**
 * Clear plan-related data from storage.
 */
export function clearPlanData(): void {
  const store = safeLocalStorage();
  if (!store) return;
  store.removeItem(KEY_PLAN);
  store.removeItem(KEY_STATUS);
  store.removeItem(KEY_TRIAL_ENDS);
  store.removeItem(KEY_USAGE);
}
