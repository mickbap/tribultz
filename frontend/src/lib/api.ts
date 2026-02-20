export type JobEvidence = {
    type: "job";
    job_id: string;
    href: string;
    label: string;
    payload?: Record<string, any> | null;
};

export type ChatMessageResponse = {
    conversation_id: string;
    response_markdown: string;
    evidence: JobEvidence[];
};

export async function postChatMessage(input: { message: string; conversation_id?: string | null }): Promise<ChatMessageResponse> {
    const res = await fetch("/api/v1/chat/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            message: input.message,
            ...(input.conversation_id ? { conversation_id: input.conversation_id } : {}),
        }),
    });

    if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`Chat error ${res.status}: ${text}`);
    }
    return res.json();
}
