import { apiGet } from "@/services/api";
import type { JobItem } from "@/types/jobs";

export default async function JobDetailPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = await params;
    const job = await apiGet<JobItem>(`/api/v1/jobs/${id}`);

    return (
        <main style={{ padding: 24 }}>
            <h1>Job Detail</h1>
            <pre
                style={{
                    background: "#111",
                    color: "#0f0",
                    padding: 16,
                    overflowX: "auto",
                }}
            >
                {JSON.stringify(job, null, 2)}
            </pre>
        </main>
    );
}
