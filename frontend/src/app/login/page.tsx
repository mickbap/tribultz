"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { setToken } from "@/auth/auth";
import { API_URL } from "@/services/api";

export default function LoginPage() {
    const router = useRouter();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [tenantSlug, setTenantSlug] = useState("default");
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setError(null);
        setLoading(true);

        try {
            const res = await fetch(`${API_URL}/api/v1/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    email,
                    password,
                    tenant_slug: tenantSlug,
                }),
            });

            if (!res.ok) {
                const body = await res.json().catch(() => ({ detail: "Login failed" }));
                setError(body.detail ?? "Login failed");
                return;
            }

            const data: { access_token: string } = await res.json();
            setToken(data.access_token);
            router.replace("/jobs");
        } catch {
            setError("Network error — could not reach the API.");
        } finally {
            setLoading(false);
        }
    }

    return (
        <main style={styles.page}>
            <form onSubmit={handleSubmit} style={styles.card}>
                <h1 style={styles.title}>Tribultz Console</h1>
                <p style={styles.subtitle}>Sign in to continue</p>

                {error && <div style={styles.error}>{error}</div>}

                <label style={styles.label}>
                    Email
                    <input
                        id="login-email"
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        style={styles.input}
                        autoComplete="email"
                    />
                </label>

                <label style={styles.label}>
                    Password
                    <input
                        id="login-password"
                        type="password"
                        required
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        style={styles.input}
                        autoComplete="current-password"
                    />
                </label>

                <label style={styles.label}>
                    Tenant
                    <input
                        id="login-tenant"
                        type="text"
                        value={tenantSlug}
                        onChange={(e) => setTenantSlug(e.target.value)}
                        style={styles.input}
                    />
                </label>

                <button
                    id="login-submit"
                    type="submit"
                    disabled={loading}
                    style={styles.button}
                >
                    {loading ? "Signing in…" : "Sign In"}
                </button>
            </form>
        </main>
    );
}

const styles: Record<string, React.CSSProperties> = {
    page: {
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
    },
    card: {
        width: 380,
        padding: 32,
        borderRadius: 12,
        background: "rgba(30,41,59,0.85)",
        backdropFilter: "blur(12px)",
        border: "1px solid rgba(148,163,184,0.15)",
        display: "flex",
        flexDirection: "column",
        gap: 16,
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
    },
    title: {
        margin: 0,
        fontSize: 24,
        fontWeight: 700,
        color: "#f8fafc",
        textAlign: "center",
    },
    subtitle: {
        margin: 0,
        fontSize: 14,
        color: "#94a3b8",
        textAlign: "center",
    },
    label: {
        display: "flex",
        flexDirection: "column",
        gap: 4,
        fontSize: 13,
        color: "#cbd5e1",
        fontWeight: 500,
    },
    input: {
        padding: "10px 12px",
        borderRadius: 8,
        border: "1px solid rgba(148,163,184,0.25)",
        background: "rgba(15,23,42,0.7)",
        color: "#f1f5f9",
        fontSize: 14,
        outline: "none",
    },
    button: {
        marginTop: 8,
        padding: "12px 0",
        borderRadius: 8,
        border: "none",
        background: "linear-gradient(135deg, #3b82f6, #6366f1)",
        color: "#fff",
        fontSize: 15,
        fontWeight: 600,
        cursor: "pointer",
    },
    error: {
        padding: "10px 12px",
        borderRadius: 8,
        background: "rgba(239,68,68,0.15)",
        border: "1px solid rgba(239,68,68,0.3)",
        color: "#fca5a5",
        fontSize: 13,
        textAlign: "center",
    },
};
