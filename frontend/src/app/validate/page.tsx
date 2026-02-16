"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/auth/auth";
import { API_URL } from "@/services/api";

type InvoiceItem = {
    sku: string;
    description: string;
    base_amount: string; // Keep as string for input
    cbs_rule_code: string;
    ibs_rule_code: string;
};

export default function ValidatePage() {
    const router = useRouter();
    const [invoiceNumber, setInvoiceNumber] = useState("");
    const [issueDate, setIssueDate] = useState("");
    const [declaredCbs, setDeclaredCbs] = useState("0");
    const [declaredIbs, setDeclaredIbs] = useState("0");
    const [items, setItems] = useState<InvoiceItem[]>([]);

    // UI state
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<string | null>(null);

    // New item state
    const [newItem, setNewItem] = useState<InvoiceItem>({
        sku: "",
        description: "",
        base_amount: "",
        cbs_rule_code: "STD_CBS",
        ibs_rule_code: "STD_IBS",
    });

    function addItem() {
        if (!newItem.base_amount || !newItem.sku) return;
        setItems([...items, newItem]);
        setNewItem({
            sku: "",
            description: "",
            base_amount: "",
            cbs_rule_code: "STD_CBS",
            ibs_rule_code: "STD_IBS",
        });
    }

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setLoading(true);
        setMessage(null);

        const token = getToken();
        if (!token) {
            router.push("/login"); // Redirect if not authenticated
            return;
        }

        try {
            const res = await fetch(`${API_URL}/api/v1/tasks/validate`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`,
                },
                body: JSON.stringify({
                    invoice_number: invoiceNumber,
                    issue_date: issueDate,
                    declared_cbs: declaredCbs,
                    declared_ibs: declaredIbs,
                    items: items,
                    async_mode: false, // Sync for immediate feedback
                }),
            });

            const data = await res.json();
            if (res.ok) {
                setMessage(`Success: ${JSON.stringify(data)}`);
            } else {
                setMessage(`Error: ${data.detail || "Validation failed"}`);
            }
        } catch (err) {
            setMessage("Network error or server unreachable.");
        } finally {
            setLoading(false);
        }
    }

    return (
        <main style={{ padding: 20 }}>
            <h1>Validate Invoice (CBS/IBS)</h1>
            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 600 }}>

                <label>
                    Invoice Number:
                    <input value={invoiceNumber} onChange={e => setInvoiceNumber(e.target.value)} required />
                </label>
                <label>
                    Issue Date:
                    <input type="date" value={issueDate} onChange={e => setIssueDate(e.target.value)} required />
                </label>
                <label>
                    Declared CBS:
                    <input type="number" step="0.01" value={declaredCbs} onChange={e => setDeclaredCbs(e.target.value)} required />
                </label>
                <label>
                    Declared IBS:
                    <input type="number" step="0.01" value={declaredIbs} onChange={e => setDeclaredIbs(e.target.value)} required />
                </label>

                <hr />
                <h3>Items</h3>
                <div>
                    <input placeholder="SKU" value={newItem.sku} onChange={e => setNewItem({ ...newItem, sku: e.target.value })} />
                    <input placeholder="Desc" value={newItem.description} onChange={e => setNewItem({ ...newItem, description: e.target.value })} />
                    <input placeholder="Amount" type="number" value={newItem.base_amount} onChange={e => setNewItem({ ...newItem, base_amount: e.target.value })} />
                    <button type="button" onClick={addItem}>Add Item</button>
                </div>
                <ul>
                    {items.map((it, idx) => (
                        <li key={idx}>{it.sku} - {it.base_amount} ({it.cbs_rule_code}/{it.ibs_rule_code})</li>
                    ))}
                </ul>

                <button type="submit" disabled={loading}>Validate</button>
            </form>
            {message && <pre style={{ marginTop: 20, background: "#eee", padding: 10 }}>{message}</pre>}
        </main>
    );
}
