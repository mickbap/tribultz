import { JobStatus } from "@/lib/types";

const styleByStatus: Record<JobStatus, string> = {
  QUEUED: "bg-slate-100 text-slate-700 border-slate-300",
  RUNNING: "bg-blue-100 text-blue-700 border-blue-300",
  SUCCESS: "bg-emerald-100 text-emerald-700 border-emerald-300",
  FAILED: "bg-rose-100 text-rose-700 border-rose-300",
};

export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${styleByStatus[status]}`}>
      {status}
    </span>
  );
}
