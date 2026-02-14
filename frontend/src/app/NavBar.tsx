"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { getToken, clearToken } from "@/auth/auth";

const CHAT_ENABLED = process.env.NEXT_PUBLIC_CHAT_ENABLED === "true";

export default function NavBar() {
    const pathname = usePathname();
    const router = useRouter();
    const isLoggedIn = typeof window !== "undefined" && !!getToken();

    // Don't show nav on login page
    if (pathname === "/login") return null;
    // Don't show nav if not logged in (will redirect anyway)
    if (!isLoggedIn) return null;

    function handleLogout() {
        clearToken();
        router.replace("/login");
    }

    return (
        <nav style={styles.nav}>
            <span style={styles.brand}>Tribultz</span>
            <div style={styles.links}>
                <Link href="/jobs" style={pathname.startsWith("/jobs") ? styles.active : styles.link}>
                    Jobs
                </Link>
                <Link href="/audit" style={pathname === "/audit" ? styles.active : styles.link}>
                    Audit
                </Link>
                {CHAT_ENABLED && (
                    <Link href="/chat" style={pathname === "/chat" ? styles.active : styles.link}>
                        Chat
                    </Link>
                )}
                <button onClick={handleLogout} style={styles.logout}>
                    Logout
                </button>
            </div>
        </nav>
    );
}

const styles: Record<string, React.CSSProperties> = {
    nav: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "12px 24px",
        background: "rgba(15,23,42,0.95)",
        borderBottom: "1px solid rgba(148,163,184,0.12)",
    },
    brand: {
        fontWeight: 700,
        fontSize: 16,
        color: "#f8fafc",
        letterSpacing: "0.04em",
    },
    links: {
        display: "flex",
        gap: 16,
        alignItems: "center",
    },
    link: {
        color: "#94a3b8",
        fontSize: 14,
        textDecoration: "none",
        padding: "4px 8px",
        borderRadius: 6,
    },
    active: {
        color: "#f8fafc",
        fontSize: 14,
        textDecoration: "none",
        padding: "4px 8px",
        borderRadius: 6,
        background: "rgba(99,102,241,0.2)",
    },
    logout: {
        background: "none",
        border: "1px solid rgba(148,163,184,0.2)",
        color: "#94a3b8",
        fontSize: 13,
        padding: "4px 12px",
        borderRadius: 6,
        cursor: "pointer",
    },
};
