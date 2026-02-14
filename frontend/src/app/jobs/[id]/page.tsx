"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AuthGuard from "@/auth/AuthGuard";
import { apiGet } from "@/services/api";
import type { JobItem } from "@/types/jobs";

function JobDetailContent() {
    const params = useParams<{ id: string }>();
    const [job, setJob] = useState<JobItem | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!params.id) return;
        apiGet<JobItem>(`/api/v1/jobs/${params.id}`)
            .then(setJob)
            .catch((err) => setError(String(err)))
            .finally(() => setLoading(false));
    }, [params.id]);

    if (loading) return <p>Loading…</p>;
    if (error) return <p style={{ color: "#f87171" }}>Error: {error}</p>;

    return (
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
    );
}

export default function JobDetailPage() {
    return (
        <AuthGuard>
            <main style={{ padding: 24 }}>
                <h1>Job Detail</h1>
                <JobDetailContent />
            </main>
        </AuthGuard>
    );
}
