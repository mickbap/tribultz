export type JobStatus =
    | "QUEUED"
    | "RUNNING"
    | "SUCCESS"
    | "FAILED"
    | "NEEDS_HUMAN";

export interface JobItem {
    id: string;
    tenant_id: string;
    name?: string | null;
    status: JobStatus;
    created_at?: string | null;
    updated_at?: string | null;
}
