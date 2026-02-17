"use client";

import React, { useState, useRef, useEffect } from "react";
import { postChatMessage, JobEvidence } from "@/lib/api";
import styles from "./chat.module.css";

// --- Components ---

function EvidenceCard({ evidence }: { evidence: JobEvidence }) {
    const isJob = evidence.type === "job";
    const icon = isJob ? "⚙️" : "🛡️"; // Gear for job, Shield for audit

    return (
        <a
            href={evidence.href}
            className={styles.evidenceCard}
            target="_blank"
            rel="noopener noreferrer"
        >
            <span className={styles.evidenceIcon}>{icon}</span>
            <span>
                <strong>{evidence.label}</strong>
                {evidence.job_id && <span style={{ opacity: 0.7 }}> #{evidence.job_id.slice(0, 8)}</span>}
            </span>
        </a>
    );
}

function SimpleMarkdown({ text }: { text: string }) {
    // Very basic MVP markdown: bold, italic, code
    // For full markdown, would need a library or complex regex

    // 1. Split by newlines for paragraphs
    const lines = text.split("\n");

    return (
        <div className={styles.markdown}>
            {lines.map((line, i) => (
                <p key={i} style={{ minHeight: line.trim() ? "auto" : "0.5em", margin: "0.2em 0" }}>
                    {processLine(line)}
                </p>
            ))}
        </div>
    );
}

function processLine(line: string): React.ReactNode {
    // Handle bold (**text**)
    const parts = line.split(/(\*\*.*?\*\*|`.*?`)/g);
    return parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
            return <strong key={i}>{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith("`") && part.endsWith("`")) {
            return <code key={i} style={{ background: "#eee", padding: "2px 4px", borderRadius: 4 }}>{part.slice(1, -1)}</code>;
        }
        return part;
    });
}

function MessageBubble({ role, content, evidence }: { role: "user" | "assistant"; content: string; evidence?: JobEvidence[] }) {
    const isUser = role === "user";

    return (
        <div className={`${styles.messageRow} ${isUser ? styles.user : styles.assistant}`}>
            <div className={styles.roleLabel}>{isUser ? "You" : "Tribultz AI"}</div>
            <div className={`${styles.bubble} ${isUser ? styles.user : styles.assistant}`}>
                {isUser ? content : <SimpleMarkdown text={content} />}
            </div>

            {evidence && evidence.length > 0 && (
                <div className={styles.evidenceContainer}>
                    {evidence.map((ev, idx) => (
                        <EvidenceCard key={idx} evidence={ev} />
                    ))}
                </div>
            )}
        </div>
    );
}

// --- Page ---

export default function ChatPage() {
    type Msg = { role: "user" | "assistant"; content: string; evidence?: JobEvidence[] };

    const [messages, setMessages] = useState<Msg[]>([]);
    const [text, setText] = useState("");
    const [loading, setLoading] = useState(false);
    const [conversationId, setConversationId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    async function onSend(e: React.FormEvent) {
        e.preventDefault();
        if (!text.trim()) return;
        setError(null);

        const userMsg = text;
        setText("");
        setMessages((m) => [...m, { role: "user", content: userMsg }]);
        setLoading(true);

        try {
            const resp = await postChatMessage({ message: userMsg, conversation_id: conversationId });
            setConversationId(resp.conversation_id);
            setMessages((m) => [
                ...m,
                { role: "assistant", content: resp.response_markdown, evidence: resp.evidence },
            ]);
        } catch (err: any) {
            setError(err?.message ?? "Failed to send message");
            // Optionally remove user message or show error state on it
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className={styles.chatContainer}>
            <header className={styles.header}>
                <h1>ChatOps Console</h1>
            </header>

            <div className={styles.messagesArea} ref={scrollRef}>
                {messages.length === 0 && (
                    <div style={{ textAlign: "center", color: "#888", marginTop: 40 }}>
                        <p>👋 Hello! I can help you validate invoices.</p>
                        <p>Try: <em>"Validate invoice INV-123"</em></p>
                    </div>
                )}

                {messages.map((m, idx) => (
                    <MessageBubble
                        key={idx}
                        role={m.role}
                        content={m.content}
                        evidence={m.evidence}
                    />
                ))}

                {loading && (
                    <div className={`${styles.messageRow} ${styles.assistant}`}>
                        <div className={`${styles.bubble} ${styles.assistant}`}>
                            <span style={{ opacity: 0.6 }}>Typing...</span>
                        </div>
                    </div>
                )}
            </div>

            {error && <div className={styles.errorMessage}>{error}</div>}

            <form onSubmit={onSend} className={styles.inputArea}>
                <input
                    className={styles.chatInput}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Type a message..."
                    disabled={loading}
                    maxLength={4000}
                />
                <button
                    className={styles.sendButton}
                    disabled={loading || !text.trim()}
                    type="submit"
                >
                    Send
                </button>
            </form>

            <div className={styles.footer}>
                Session: {conversationId ? conversationId.slice(0, 8) + "..." : "(new)"}
            </div>
        </div>
    );
}
