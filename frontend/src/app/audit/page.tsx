"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import AuthGuard from "@/auth/AuthGuard";
import { apiGet } from "@/services/api";
import type { AuditSearchResponse, AuditLogItem } from "@/types/audit";

function q(params: Record<string, string | undefined>) {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) sp.set(k, v);
    const s = sp.toString();
    return s ? `?${s}` : "";
}

function AuditContent() {
    const searchParams = useSearchParams();
    const action = searchParams.get("action") ?? undefined;
    const entity = searchParams.get("entity") ?? undefined;
    const limit = searchParams.get("limit") ?? "50";
    const offset = searchParams.get("offset") ?? "0";

    const [items, setItems] = useState<AuditLogItem[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const qs = q({ action, entity, limit, offset });
        apiGet<AuditSearchResponse>(`/api/v1/audit/search${qs}`)
            .then((data) => setItems(data.items ?? []))
            .catch((err) => setError(String(err)))
            .finally(() => setLoading(false));
    }, [action, entity, limit, offset]);

    if (loading) return <p>Loading…</p>;
    if (error) return <p style={{ color: "#f87171" }}>Error: {error}</p>;

    return (
        <>
            <form style={{ display: "flex", gap: 12, margin: "12px 0" }}>
                <input name="action" placeholder="action" defaultValue={action ?? ""} />
                <input name="entity" placeholder="entity" defaultValue={entity ?? ""} />
                <input name="limit" placeholder="limit" defaultValue={limit} style={{ width: 100 }} />
                <input name="offset" placeholder="offset" defaultValue={offset} style={{ width: 100 }} />
                <button type="submit">Buscar</button>
            </form>

            <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                    <tr>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Quando</th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Action</th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Entity</th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Entity ID</th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Checksum</th>
                    </tr>
                </thead>
                <tbody>
                    {items.map((it) => (
                        <tr key={it.id}>
                            <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>{it.created_at ?? ""}</td>
                            <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>{it.action}</td>
                            <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>{it.entity ?? ""}</td>
                            <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>{it.entity_id ?? ""}</td>
                            <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", fontFamily: "monospace" }}>{it.checksum ?? ""}</td>
                        </tr>
                    ))}
                </tbody>
            </table>

            <div style={{ marginTop: 12, display: "flex", gap: 12 }}>
                <a
                    href={`/audit${q({
                        action,
                        entity,
                        limit,
                        offset: String(Math.max(0, Number(offset) - Number(limit))),
                    })}`}
                >
                    ← Prev
                </a>
                <a
                    href={`/audit${q({
                        action,
                        entity,
                        limit,
                        offset: String(Number(offset) + Number(limit)),
                    })}`}
                >
                    Next →
                </a>
            </div>
        </>
    );
}

export default function AuditPage() {
    return (
        <AuthGuard>
            <main style={{ padding: 24 }}>
                <h1>Auditoria</h1>
                <p>Busca read-only no audit log.</p>
                <AuditContent />
            </main>
        </AuthGuard>
    );
}
