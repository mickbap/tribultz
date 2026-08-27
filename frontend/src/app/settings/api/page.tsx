"use client";

import { useEffect, useState } from "react";
import { Toast } from "@/components/common/Toast";
import { API_BASE } from "@/lib/api";
import { formatDateTimeBR } from "@/lib/formatDateTimeBR";
import { getToken, getTenantId } from "@/lib/storage";

interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  credits_balance: number;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${getToken()}`,
    "X-Tenant-Id": getTenantId(),
  };
}

export default function ApiSettingsPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [newName, setNewName] = useState("");
  const [loading, setLoading] = useState(false);
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [toast, setToast] = useState<{ tone: "success" | "error" | "info"; message: string } | null>(null);

  const showToast = (tone: "success" | "error" | "info", message: string) => {
    setToast({ tone, message });
    setTimeout(() => setToast(null), 4000);
  };

  async function loadKeys() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/api-keys`, { headers: authHeaders() });
      if (!res.ok) throw new Error(await res.text());
      setKeys(await res.json());
    } catch {
      showToast("error", "Erro ao carregar API Keys.");
    }
  }

  useEffect(() => { loadKeys(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function createKey() {
    if (!newName.trim()) { showToast("error", "Informe um nome para a chave."); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/api-keys`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ name: newName.trim() }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Erro ao criar chave.");
      }
      const data = await res.json();
      setRevealedKey(data.key);
      setNewName("");
      await loadKeys();
      showToast("success", "API Key criada! Copie a chave agora — ela não será exibida novamente.");
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Erro ao criar chave.");
    } finally {
      setLoading(false);
    }
  }

  async function revokeKey(id: string) {
    if (!confirm("Revogar esta API Key? Integrações que a usam pararão de funcionar.")) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/api-keys/${id}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error();
      setRevealedKey(null);
      await loadKeys();
      showToast("success", "API Key revogada.");
    } catch {
      showToast("error", "Erro ao revogar chave.");
    }
  }

  async function copyKey(text: string) {
    await navigator.clipboard.writeText(text);
    showToast("info", "Chave copiada para a área de transferência.");
  }

  return (
    <section className="space-y-6">
      {toast && <Toast tone={toast.tone} message={toast.message} onClose={() => setToast(null)} />}

      <header>
        <h1 className="text-2xl font-bold text-slate-900">API Keys</h1>
        <p className="text-sm text-slate-500 mt-1">
          Autentique integrações ERP e sistemas externos com a API pay-per-call.
          Cada chamada a <code className="bg-slate-100 px-1 rounded text-xs">/classify</code> consome 1 crédito.
          O cálculo CBS/IBS é completo. A classificação NCM→cClassTrib é retornada como{" "}
          <strong>candidatos com base legal</strong>, nunca como código único: o NCM delimita
          os tratamentos possíveis, mas quem determina é o contexto da operação.
        </p>
      </header>

      {/* Nova key */}
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-800 mb-3">Criar nova API Key</h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createKey()}
            placeholder="Ex: ERP Producao, TOTVS Homologação"
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            maxLength={80}
          />
          <button
            type="button"
            onClick={createKey}
            disabled={loading}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Criando…" : "Criar Key"}
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          100 créditos grátis na criação. Limite de 5 keys ativas por conta.
        </p>
      </section>

      {/* Chave recém-criada */}
      {revealedKey && (
        <section className="rounded-xl border border-amber-300 bg-amber-50 p-5">
          <p className="text-sm font-semibold text-amber-800 mb-2">
            ⚠️ Copie agora — esta chave não será exibida novamente.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded bg-white border border-amber-200 px-3 py-2 text-xs font-mono break-all text-slate-700">
              {revealedKey}
            </code>
            <button
              type="button"
              onClick={() => copyKey(revealedKey)}
              className="shrink-0 rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-medium text-amber-800 hover:bg-amber-100"
            >
              Copiar
            </button>
          </div>
        </section>
      )}

      {/* Lista de keys */}
      <section className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-800">Suas API Keys</h2>
        </div>
        {keys.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-slate-400">
            Nenhuma API Key criada ainda.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-xs text-slate-500 text-left">
                <th className="px-5 py-3 font-medium">Nome</th>
                <th className="px-5 py-3 font-medium">Prefixo</th>
                <th className="px-5 py-3 font-medium">Créditos</th>
                <th className="px-5 py-3 font-medium">Último uso</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {keys.map((k) => (
                <tr key={k.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-3 font-medium text-slate-800">{k.name}</td>
                  <td className="px-5 py-3 font-mono text-xs text-slate-500">{k.key_prefix}</td>
                  <td className="px-5 py-3">
                    <span className={`font-semibold ${k.credits_balance === 0 ? "text-red-600" : k.credits_balance < 20 ? "text-amber-600" : "text-green-700"}`}>
                      {k.credits_balance.toLocaleString("pt-BR")}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-xs text-slate-400">
                    {k.last_used_at
                      ? formatDateTimeBR(k.last_used_at)
                      : "Nunca usado"}
                  </td>
                  <td className="px-5 py-3">
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${k.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                      {k.is_active ? "Ativa" : "Revogada"}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    {k.is_active && (
                      <button
                        type="button"
                        onClick={() => revokeKey(k.id)}
                        className="text-xs text-red-500 hover:text-red-700 font-medium"
                      >
                        Revogar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Documentação rápida */}
      <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <h2 className="text-base font-semibold text-slate-800">Como usar</h2>
        <div>
          <p className="text-xs font-medium text-slate-500 mb-1">POST /api/v1/public-api/classify</p>
          <pre className="rounded-lg bg-slate-900 text-slate-100 text-xs p-4 overflow-x-auto">{`curl -X POST https://api.tribultz.com.br/api/v1/public-api/classify \\
  -H "X-API-Key: tribultz_sk_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "ncm": "02013000",
    "uf_destino": "SP",
    "base_value": "150.00",
    "cst": "000"
  }'`}</pre>
        </div>
        <div>
          <p className="text-xs font-medium text-slate-500 mb-1">Resposta</p>
          <pre className="rounded-lg bg-slate-900 text-slate-100 text-xs p-4 overflow-x-auto">{`{
  "ncm": "02013000",
  "cClassTrib": null,
  "cclasstrib_status": "candidato_unico",
  "cclasstrib_candidatos": [
    {
      "codigo": "200003",
      "descricao": "Vendas de produtos destinados à alimentação humana...",
      "base_legal": "Anexo 1 — LC 214"
    }
  ],
  "cst": "000",
  "vBC": "150.00",
  "vCBS": "13.20",
  "vIBS": "26.55",
  "total_tributos": "39.75",
  "aliquota_efetiva_pct": "26.50",
  "xml_snippet": "<IBSCBS>...</IBSCBS>",
  "credits_used": 1,
  "credits_remaining": 99
}`}</pre>
        </div>
      </section>
    </section>
  );
}
