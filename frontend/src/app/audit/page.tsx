import { apiGet } from "@/services/api";
import type { AuditSearchResponse } from "@/types/audit";

function q(params: Record<string, string | undefined>) {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) sp.set(k, v);
    const s = sp.toString();
    return s ? `?${s}` : "";
}

export default async function AuditPage({
    searchParams,
}: {
    searchParams: Promise<{
        action?: string;
        entity?: string;
        limit?: string;
        offset?: string;
    }>;
}) {
    const sp = await searchParams;
    const limit = sp.limit ?? "50";
    const offset = sp.offset ?? "0";

    const qs = q({
        action: sp.action,
        entity: sp.entity,
        limit,
        offset,
    });

    const data = await apiGet<AuditSearchResponse>(`/api/v1/audit/search${qs}`);

    return (
        <main style={{ padding: 24 }}>
            <h1>Auditoria</h1>
            <p>Busca read-only no audit log.</p>

            <form style={{ display: "flex", gap: 12, margin: "12px 0" }}>
                <input name="action" placeholder="action" defaultValue={sp.action ?? ""} />
                <input name="entity" placeholder="entity" defaultValue={sp.entity ?? ""} />
                <input name="limit" placeholder="limit" defaultValue={limit} style={{ width: 100 }} />
                <input name="offset" placeholder="offset" defaultValue={offset} style={{ width: 100 }} />
                <button type="submit">Buscar</button>
            </form>

            <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                    <tr>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                            Quando
                        </th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                            Action
                        </th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                            Entity
                        </th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                            Entity ID
                        </th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                            Checksum
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {(data.items ?? []).map((it) => (
                        <tr key={it.id}>
                            <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>
                                {it.created_at ?? ""}
                            </td>
                            <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>
                                {it.action}
                            </td>
                            <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>
                                {it.entity ?? ""}
                            </td>
                            <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>
                                {it.entity_id ?? ""}
                            </td>
                            <td
                                style={{
                                    padding: 8,
                                    borderBottom: "1px solid #f0f0f0",
                                    fontFamily: "monospace",
                                }}
                            >
                                {it.checksum ?? ""}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>

            <div style={{ marginTop: 12, display: "flex", gap: 12 }}>
                <a
                    href={`/audit${q({
                        action: sp.action,
                        entity: sp.entity,
                        limit,
                        offset: String(Math.max(0, Number(offset) - Number(limit))),
                    })}`}
                >
                    ← Prev
                </a>
                <a
                    href={`/audit${q({
                        action: sp.action,
                        entity: sp.entity,
                        limit,
                        offset: String(Number(offset) + Number(limit)),
                    })}`}
                >
                    Next →
                </a>
            </div>
        </main>
    );
}
