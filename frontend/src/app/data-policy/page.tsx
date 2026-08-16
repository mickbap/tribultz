/**
 * /data-policy — política de tratamento de dados do diagnóstico público (#637).
 *
 * A resposta de FAQ em JSON-LD (`schemas.ts`) mandava o leitor para
 * `/api/v1/public/data-policy` — caminho RELATIVO. A API vive em host próprio
 * (`api.tribultz.com.br`), então no domínio do site esse caminho resolvia para
 * o apex e devolvia 404. Como a frase vive num FAQ que o Google pode exibir
 * como rich result, quem clicasse caía num 404; e mesmo com a URL correta da
 * API cairia num JSON cru.
 *
 * Esta página consome o endpoint (que segue sendo a fonte da verdade) e o
 * apresenta em linguagem de leitor. Revalida de hora em hora; se a API estiver
 * fora no momento do build ou da revalidação, cai num texto mínimo com o link
 * absoluto — política de privacidade que renderiza desatualizada é aceitável,
 * política que renderiza erro não é.
 */

import type { Metadata } from "next";
import { LegalPageLayout } from "@/components/legal/LegalPageLayout";
import { API_BASE } from "@/lib/api";

export const metadata: Metadata = {
  alternates: { canonical: "/data-policy" },
  title: "Política de Dados do Diagnóstico Gratuito",
  description:
    "Como o XML enviado ao diagnóstico gratuito da Tribultz é tratado: sem armazenamento, sem extração de dados pessoais, descarte imediato.",
};

export const revalidate = 3600;

type Commitment = { id: string; title: string; description: string };
type DataPolicy = {
  service?: string;
  version?: string;
  effective_date?: string;
  commitments?: Commitment[];
};

const POLICY_URL = `${API_BASE}/api/v1/public/data-policy`;

async function carregarPolitica(): Promise<DataPolicy | null> {
  try {
    const res = await fetch(POLICY_URL, { next: { revalidate } });
    if (!res.ok) return null;
    return (await res.json()) as DataPolicy;
  } catch {
    return null;
  }
}

function formatarData(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00-03:00`);
  return Number.isNaN(d.getTime())
    ? "—"
    : new Intl.DateTimeFormat("pt-BR", {
        timeZone: "America/Sao_Paulo",
        day: "2-digit",
        month: "long",
        year: "numeric",
      }).format(d);
}

export default async function DataPolicyPage() {
  const politica = await carregarPolitica();
  const compromissos = politica?.commitments ?? [];

  return (
    <LegalPageLayout
      title="Política de Dados do Diagnóstico Gratuito"
      updatedAt={formatarData(politica?.effective_date)}
      summary="O que acontece com o XML que você envia ao diagnóstico gratuito — e o que explicitamente não acontece."
    >
      {compromissos.length > 0 ? (
        <div className="space-y-6">
          {compromissos.map((c) => (
            <div key={c.id}>
              <h2 className="text-lg font-semibold text-slate-900">{c.title}</h2>
              <p className="mt-2 leading-7 text-slate-700">{c.description}</p>
            </div>
          ))}
          <p className="border-t border-slate-200 pt-6 text-sm text-slate-500">
            Versão {politica?.version ?? "—"} desta política. A fonte é o endpoint
            público{" "}
            <a href={POLICY_URL} className="text-tribultz-700 underline" rel="nofollow">
              {POLICY_URL}
            </a>
            , consultável a qualquer momento.
          </p>
        </div>
      ) : (
        <p className="leading-7 text-slate-700">
          A versão detalhada desta política está publicada no endpoint{" "}
          <a href={POLICY_URL} className="text-tribultz-700 underline" rel="nofollow">
            {POLICY_URL}
          </a>
          . O XML enviado ao diagnóstico gratuito é processado em memória e descartado
          imediatamente — nada é gravado em banco, disco ou object storage.
        </p>
      )}
    </LegalPageLayout>
  );
}
