"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/auth/auth";
import { API_URL } from "@/services/api";

export default function ReportPage() {
    const router = useRouter();
    const [companyName, setCompanyName] = useState("");
    const [cnpj, setCnpj] = useState("");
    const [refPeriod, setRefPeriod] = useState("");
    const [invoicesJson, setInvoicesJson] = useState("[]");

    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<string | null>(null);

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setLoading(true);
        setMessage(null);

        const token = getToken();
        if (!token) {
            router.push("/login");
            return;
        }

        try {
            let parsedInvoices = [];
            try {
                parsedInvoices = JSON.parse(invoicesJson);
            } catch (jsonErr) {
                setMessage("Error parsing Invoices JSON");
                setLoading(false);
                return;
            }

            const res = await fetch(`${API_URL}/api/v1/tasks/report`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`,
                },
                body: JSON.stringify({
                    company_name: companyName,
                    cnpj: cnpj,
                    reference_period: refPeriod,
                    invoices: parsedInvoices,
                    async_mode: false
                }),
            });

            const data = await res.json();
            if (res.ok) {
                setMessage(`Report Generated. Task ID: ${data.task_id || "N/A"}\nResult: ${JSON.stringify(data)}`);
            } else {
                setMessage(`Error: ${data.detail || "Report generation failed"}`);
            }
        } catch (err) {
            setMessage("Network error or server unreachable.");
        } finally {
            setLoading(false);
        }
    }

    const sampleJson = `[
  {
    "invoice_number": "INV-001",
    "declared_cbs": "10.00",
    "declared_ibs": "15.00",
    "items": [
      { "base_amount": "100.00" }
    ]
  }
]`;

    return (
        <main style={{ padding: 20 }}>
            <h1>Generate Compliance Report</h1>
            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 600 }}>
                <label>
                    Company Name:
                    <input value={companyName} onChange={e => setCompanyName(e.target.value)} required />
                </label>
                <label>
                    CNPJ:
                    <input value={cnpj} onChange={e => setCnpj(e.target.value)} required />
                </label>
                <label>
                    Period (YYYY-MM):
                    <input type="month" value={refPeriod} onChange={e => setRefPeriod(e.target.value)} required />
                </label>

                <label>
                    Invoices (JSON):
                    <textarea
                        rows={10}
                        value={invoicesJson}
                        onChange={e => setInvoicesJson(e.target.value)}
                        placeholder={sampleJson}
                        style={{ fontFamily: 'monospace' }}
                    />
                </label>
                <small style={{ color: "#666" }}>Paste JSON matching TaskBInvoice structure.</small>

                <button type="submit" disabled={loading}>Generate Report</button>
            </form>
            {message && <pre style={{ marginTop: 20, background: "#eee", padding: 10, whiteSpace: "pre-wrap" }}>{message}</pre>}
        </main>
    );
}
