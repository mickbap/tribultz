"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AuthGuard from "@/auth/AuthGuard";
import { apiGet } from "@/services/api";
import type { JobItem } from "@/types/jobs";

function JobsContent() {
    const [jobs, setJobs] = useState<JobItem[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        apiGet<JobItem[]>("/api/v1/jobs")
            .then(setJobs)
            .catch((err) => setError(String(err)))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <p>Loading…</p>;
    if (error) return <p style={{ color: "#f87171" }}>Error: {error}</p>;

    return (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
                <tr>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                        ID
                    </th>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                        Status
                    </th>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                        Tenant
                    </th>
                </tr>
            </thead>
            <tbody>
                {jobs.map((j) => (
                    <tr key={j.id}>
                        <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>
                            <Link href={`/jobs/${j.id}`}>{j.id}</Link>
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>
                            {j.status}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>
                            {j.tenant_id}
                        </td>
                    </tr>
                ))}
            </tbody>
        </table>
    );
}

export default function JobsPage() {
    return (
        <AuthGuard>
            <main style={{ padding: 24 }}>
                <h1>Jobs</h1>
                <p>Lista de execuções (read-only).</p>
                <JobsContent />
            </main>
        </AuthGuard>
    );
}
