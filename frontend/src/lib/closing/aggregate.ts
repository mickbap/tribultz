import { AuditLog, ExceptionRequest, Job } from "../types";

export type ClosingSnapshot = {
  since: string;
  until: string;
  counts: {
    fatalFindings: number;
    openExceptions: number;
    jobsExecuted: number;
    recentAudits: number;
  };
  recentJobs: Job[];
  recentAuditRows: AuditLog[];
  openExceptionRows: ExceptionRequest[];
};

type ClosingInput = {
  jobs: Job[];
  audits: AuditLog[];
  exceptions: ExceptionRequest[];
  now?: Date;
  days?: number;
  listLimit?: number;
};

const DAY_MS = 24 * 60 * 60 * 1000;

function toTs(value: string | undefined): number | null {
  if (!value) return null;
  const ts = new Date(value).getTime();
  return Number.isNaN(ts) ? null : ts;
}

function inWindow(ts: number | null, startTs: number, endTs: number): boolean {
  return ts !== null && ts >= startTs && ts <= endTs;
}

function byDateDesc<T>(rows: T[], getDate: (row: T) => string): T[] {
  return [...rows].sort((a, b) => {
    const aTs = toTs(getDate(a)) ?? 0;
    const bTs = toTs(getDate(b)) ?? 0;
    return bTs - aTs;
  });
}

export function createClosingSnapshot({
  jobs,
  audits,
  exceptions,
  now = new Date(),
  days = 7,
  listLimit = 5,
}: ClosingInput): ClosingSnapshot {
  const endTs = now.getTime();
  const startTs = endTs - days * DAY_MS;
  const since = new Date(startTs).toISOString();
  const until = now.toISOString();

  const jobsInWindow = jobs.filter((job) => inWindow(toTs(job.createdAt), startTs, endTs));
  const auditsInWindow = audits.filter((row) => inWindow(toTs(row.createdAt), startTs, endTs));
  const openExceptionsInWindow = exceptions.filter(
    (row) => row.status === "OPEN" && inWindow(toTs(row.created_at), startTs, endTs),
  );

  const fatalFindings = jobsInWindow.reduce((total, job) => {
    const current = (job.findings ?? []).filter((finding) => finding.severity === "FATAL").length;
    return total + current;
  }, 0);

  return {
    since,
    until,
    counts: {
      fatalFindings,
      openExceptions: openExceptionsInWindow.length,
      jobsExecuted: jobsInWindow.length,
      recentAudits: auditsInWindow.length,
    },
    recentJobs: byDateDesc(jobsInWindow, (job) => job.createdAt).slice(0, listLimit),
    recentAuditRows: byDateDesc(auditsInWindow, (row) => row.createdAt).slice(0, listLimit),
    openExceptionRows: byDateDesc(openExceptionsInWindow, (row) => row.created_at).slice(0, listLimit),
  };
}
