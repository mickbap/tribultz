import type { Metadata } from "next";
import { LegalPageLayout } from "@/components/legal/LegalPageLayout";

export const metadata: Metadata = {
  alternates: { canonical: "/lgpd" },
  title: "LGPD",
  description: "Como a Tribultz trata seus dados pessoais de acordo com a LGPD.",
};

export default function LGPDPage() {
  return (
    <LegalPageLayout
      title="LGPD na Tribultz"
      updatedAt="10 de abril de 2026"
      summary="Esta página resume como aplicamos a Lei Geral de Proteção de Dados no produto, nas ferramentas públicas e no console, com foco prático em segurança, governança e exercício de direitos."
    >
      <section>
        <h2 className="text-lg font-semibold text-slate-900">1. Nosso compromisso</h2>
        <p>
          A Tribultz aplica princípios de finalidade, necessidade, segurança, transparência,
          prevenção e responsabilização no tratamento de dados pessoais. O objetivo é sustentar
          a operação fiscal do cliente sem abrir mão de governança e rastreabilidade.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">2. Como a LGPD entra na operação</h2>
        <ul className="mt-3 list-disc space-y-2 pl-6">
          <li>Controle de acesso por tenant e segregação lógica de dados.</li>
          <li>Criptografia em trânsito, trilha auditável e retenção compatível com obrigação legal.</li>
          <li>Processamento mínimo necessário para autenticação, cobrança, suporte e rotina fiscal.</li>
          <li>Uso de operadores especializados apenas quando indispensáveis à prestação do serviço.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">3. Bases legais mais relevantes</h2>
        <ul className="mt-3 list-disc space-y-2 pl-6">
          <li><strong>Execução de contrato:</strong> acesso à plataforma e entrega das funcionalidades contratadas.</li>
          <li><strong>Obrigação legal e regulatória:</strong> guarda e auditoria de registros quando exigido.</li>
          <li><strong>Legítimo interesse:</strong> segurança, prevenção a fraude e continuidade operacional.</li>
          <li><strong>Consentimento:</strong> quando a lei ou a natureza do fluxo exigirem autorização específica.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">4. Direitos do titular</h2>
        <p>
          O titular pode pedir confirmação de tratamento, acesso, correção, anonimização, portabilidade,
          eliminação quando cabível, revisão e informações sobre compartilhamento.
        </p>
        <p className="mt-2">
          No console, os fluxos de exportação e solicitação ficam em
          <strong> Configurações &gt; Meus Dados (LGPD)</strong>.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">5. Segurança e incidentes</h2>
        <p>
          Mantemos controles técnicos e operacionais para reduzir risco de acesso indevido,
          perda, alteração não autorizada e indisponibilidade. Havendo incidente relevante,
          a resposta seguirá a legislação aplicável e o plano interno de tratamento.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">6. Canal do DPO</h2>
        <p>
          Solicitações relacionadas à proteção de dados podem ser enviadas para
          <strong> dpo@tribultz.com.br</strong>.
        </p>
      </section>
    </LegalPageLayout>
  );
}
