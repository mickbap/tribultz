import type { Metadata } from "next";
import { LegalPageLayout } from "@/components/legal/LegalPageLayout";

export const metadata: Metadata = {
  title: "Privacidade",
  description: "Política de privacidade da plataforma Tribultz.",
};

export default function PrivacyPage() {
  return (
    <LegalPageLayout
      title="Política de Privacidade"
      updatedAt="10 de abril de 2026"
      summary="Esta política descreve quais dados a Tribultz trata, por que tratamos, com quem compartilhamos e como o usuário pode exercer seus direitos em toda a stack pública e autenticada."
    >
      <section>
        <h2 className="text-lg font-semibold text-slate-900">1. Quem trata os dados</h2>
        <p>
          A Tribultz trata dados pessoais e operacionais para viabilizar cadastro, autenticação,
          cobrança, suporte, auditoria, relatórios e execução das ferramentas fiscais. Dependendo
          do contexto, atuamos como controladora de dados cadastrais e de conta, e como operadora
          ou co-controladora no processamento necessário para os fluxos fiscais contratados.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">2. Categorias de dados tratados</h2>
        <ul className="mt-3 list-disc space-y-2 pl-6">
          <li>
            <strong>Cadastro e acesso:</strong> nome, e-mail, telefone, CNPJ, tenant, credenciais
            protegidas por hash e dados necessários para autenticação.
          </li>
          <li>
            <strong>Operação fiscal:</strong> XMLs, resultados de validação, findings, evidências,
            jobs, relatórios e trilhas auditáveis geradas nas ferramentas.
          </li>
          <li>
            <strong>Cobrança:</strong> metadados de cliente, assinatura, PIX e pagamentos processados
            por provedores externos especializados, como o Asaas.
          </li>
          <li>
            <strong>Segurança e suporte:</strong> IP, user-agent, logs técnicos, eventos de auditoria,
            indicadores de abuso e interações de suporte.
          </li>
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">3. Finalidades e bases legais</h2>
        <ul className="mt-3 list-disc space-y-2 pl-6">
          <li>
            <strong>Execução contratual:</strong> liberar acesso, processar validações, relatórios,
            diagnósticos, memórias e evidências.
          </li>
          <li>
            <strong>Obrigação legal e regulatória:</strong> preservar registros exigidos por normas
            fiscais, contábeis, de segurança e de prevenção a fraude.
          </li>
          <li>
            <strong>Legítimo interesse:</strong> monitorar estabilidade, proteger a plataforma,
            prevenir abuso e melhorar a operação do produto.
          </li>
          <li>
            <strong>Consentimento, quando aplicável:</strong> comunicações opt-in e fluxos que
            exijam autorização específica do titular.
          </li>
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">4. Compartilhamento e operadores</h2>
        <p>
          A Tribultz compartilha dados apenas com operadores estritamente necessários para operar
          o serviço, sempre sob obrigações contratuais e técnicas de confidencialidade.
        </p>
        <ul className="mt-3 list-disc space-y-2 pl-6">
          <li>Infraestrutura e borda: Cloudflare e Vercel.</li>
          <li>Backend, banco e armazenamento soberano: Magalu Cloud e serviços compatíveis.</li>
          <li>Fila, cache e memória operacional: Redis.</li>
          <li>Cobrança e pagamentos: Asaas.</li>
          <li>Comunicação transacional: provedores SMTP e serviços de e-mail configurados pela operação.</li>
        </ul>
        <p className="mt-2">
          Não comercializamos dados pessoais nem compartilhamos documentos fiscais para publicidade
          comportamental.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">5. Segurança e retenção</h2>
        <ul className="mt-3 list-disc space-y-2 pl-6">
          <li>Criptografia em trânsito e em repouso, isolamento por tenant e controles de acesso.</li>
          <li>Logs de auditoria e rastreabilidade para operações críticas.</li>
          <li>
            Os XMLs e demais documentos fiscais enviados são retidos por <strong>12 meses</strong> a
            partir do envio; depois disso, são apagados automaticamente do armazenamento e do banco
            de dados.
          </li>
          <li>
            Anonimização ou exclusão de dados pessoais quando a retenção não for mais necessária
            ou quando houver obrigação legal compatível com o pedido do titular.
          </li>
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">6. Direitos do titular</h2>
        <p>
          Você pode solicitar confirmação de tratamento, acesso, correção, portabilidade, revisão,
          anonimização, exclusão quando cabível e informações sobre compartilhamento.
        </p>
        <p className="mt-2">
          Dentro do console, os fluxos de exportação e solicitação relacionados à LGPD ficam em
          <strong> Configurações &gt; Meus Dados (LGPD)</strong>.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">7. Contato</h2>
        <p>
          Para dúvidas sobre privacidade ou exercício de direitos, fale com o Encarregado de Dados
          em <strong>dpo@tribultz.com.br</strong>.
        </p>
      </section>
    </LegalPageLayout>
  );
}
