"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import AuthGuard from "@/auth/AuthGuard";

const CHAT_ENABLED = process.env.NEXT_PUBLIC_CHAT_ENABLED === "true";

function ChatContent() {
    const router = useRouter();

    useEffect(() => {
        if (!CHAT_ENABLED) {
            router.replace("/jobs");
        }
    }, [router]);

    if (!CHAT_ENABLED) return null;

    return (
        <main style={{ padding: 24 }}>
            <h1>Chat</h1>
            <div
                style={{
                    marginTop: 24,
                    padding: 32,
                    borderRadius: 12,
                    background: "rgba(30,41,59,0.6)",
                    border: "1px solid rgba(148,163,184,0.15)",
                    textAlign: "center",
                }}
            >
                <p style={{ fontSize: 18, color: "#94a3b8", margin: 0 }}>
                    🚧 <strong>Coming Soon</strong>
                </p>
                <p style={{ fontSize: 14, color: "#64748b", marginTop: 8 }}>
                    The chat assistant is under development and will be available in a
                    future sprint.
                </p>
            </div>
        </main>
    );
}

export default function ChatPage() {
    return (
        <AuthGuard>
            <ChatContent />
        </AuthGuard>
    );
}
