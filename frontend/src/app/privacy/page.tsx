export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-bold text-slate-900">Política de Privacidade</h1>
      <p className="mt-2 text-sm text-slate-500">Última atualização: 22 de março de 2026</p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-slate-700">
        <section>
          <h2 className="text-lg font-semibold text-slate-900">1. Controlador dos Dados</h2>
          <p>
            Tribultz Tecnologia Ltda. (&quot;Tribultz&quot;, &quot;nós&quot;) é a controladora dos dados pessoais
            coletados por meio desta plataforma, nos termos da Lei Geral de Proteção de Dados
            Pessoais (Lei n. 13.709/2018 — LGPD).
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">2. Dados Coletados</h2>
          <p>Coletamos os seguintes dados para prestação do serviço:</p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li><strong>Dados cadastrais:</strong> nome completo, e-mail, CNPJ da empresa, senha (armazenada com hash criptográfico).</li>
            <li><strong>Dados fiscais:</strong> notas fiscais (XML NFS-e / NF-e) enviadas para validação, resultados de validação, findings e evidências.</li>
            <li><strong>Dados de uso:</strong> logs de auditoria, histórico de jobs, mensagens de chat com assistente fiscal.</li>
            <li><strong>Dados técnicos:</strong> endereço IP, user-agent, timestamps de acesso.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">3. Finalidade do Tratamento</h2>
          <p>Seus dados são tratados para as seguintes finalidades:</p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li>Prestação do serviço de validação fiscal CBS/IBS conforme reforma tributária (LC 214 + LC 227).</li>
            <li>Geração de relatórios auditáveis e trilha de evidências.</li>
            <li>Autenticação e controle de acesso multi-tenant.</li>
            <li>Comunicação sobre o serviço e suporte técnico.</li>
            <li>Cumprimento de obrigações legais e regulatórias.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">4. Base Legal (Art. 7, LGPD)</h2>
          <p>O tratamento de dados é realizado com base em:</p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li><strong>Consentimento (Art. 7, I):</strong> fornecido no momento do cadastro.</li>
            <li><strong>Execução de contrato (Art. 7, V):</strong> necessário para prestação do serviço contratado.</li>
            <li><strong>Obrigação legal (Art. 7, II):</strong> retenção de registros fiscais conforme legislação tributária.</li>
            <li><strong>Interesse legítimo (Art. 7, IX):</strong> segurança da plataforma e prevenção a fraudes.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">5. Custódia de Dados Financeiros</h2>
          <p>
            Ao utilizar a plataforma Tribultz, você nos confia dados financeiros e fiscais de sua
            empresa. Atuamos como <strong>custodiantes</strong> desses dados, aplicando:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li>Criptografia em trânsito (TLS/SSL) e em repouso.</li>
            <li>Isolamento multi-tenant — dados de cada empresa são segregados logicamente.</li>
            <li>Checksums SHA-256 na trilha de auditoria para garantir integridade.</li>
            <li>Controle de acesso baseado em funções (RBAC).</li>
            <li>Backups regulares com retenção conforme política de retenção fiscal.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">6. Compartilhamento de Dados</h2>
          <p>
            Não compartilhamos seus dados pessoais ou fiscais com terceiros, exceto:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li>Provedores de infraestrutura (hospedagem em nuvem) sob acordo de confidencialidade.</li>
            <li>Determinação judicial ou requisição de autoridade competente.</li>
            <li>Com seu consentimento expresso para fins específicos.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">7. Seus Direitos (Art. 18, LGPD)</h2>
          <p>Você tem direito a:</p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li><strong>Acesso:</strong> solicitar cópia de todos os seus dados pessoais.</li>
            <li><strong>Correção:</strong> corrigir dados incompletos, inexatos ou desatualizados.</li>
            <li><strong>Anonimização/Eliminação:</strong> solicitar exclusão de dados desnecessários ou tratados em desconformidade.</li>
            <li><strong>Portabilidade:</strong> exportar seus dados em formato estruturado.</li>
            <li><strong>Revogação do consentimento:</strong> retirar o consentimento a qualquer momento.</li>
            <li><strong>Informação:</strong> saber com quem seus dados foram compartilhados.</li>
          </ul>
          <p className="mt-2">
            Para exercer seus direitos, acesse <strong>Configurações &gt; Meus Dados (LGPD)</strong> na
            plataforma ou entre em contato pelo e-mail: <strong>dpo@tribultz.com.br</strong>.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">8. Retenção de Dados</h2>
          <p>
            Dados fiscais são retidos pelo período exigido pela legislação tributária brasileira
            (mínimo 5 anos após o exercício fiscal). Dados cadastrais são mantidos enquanto a conta
            estiver ativa. Após solicitação de exclusão, dados pessoais são anonimizados, preservando
            registros fiscais conforme obrigação legal.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">9. Segurança</h2>
          <p>
            Adotamos medidas técnicas e organizacionais para proteger seus dados, incluindo:
            criptografia, controle de acesso, monitoramento de segurança (SOC), auditorias
            periódicas e treinamento da equipe.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">10. Encarregado de Dados (DPO)</h2>
          <p>
            Para questões relacionadas à proteção de dados pessoais, entre em contato com nosso
            Encarregado de Dados (DPO): <strong>dpo@tribultz.com.br</strong>.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">11. Alterações</h2>
          <p>
            Esta política pode ser atualizada periodicamente. Alterações significativas serão
            comunicadas por e-mail ou notificação na plataforma.
          </p>
        </section>
      </div>
    </main>
  );
}
