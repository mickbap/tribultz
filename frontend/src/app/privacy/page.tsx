export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-bold text-slate-900">Politica de Privacidade</h1>
      <p className="mt-2 text-sm text-slate-500">Ultima atualizacao: 22 de marco de 2026</p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-slate-700">
        <section>
          <h2 className="text-lg font-semibold text-slate-900">1. Controlador dos Dados</h2>
          <p>
            Tribultz Tecnologia Ltda. (&quot;Tribultz&quot;, &quot;nos&quot;) e a controladora dos dados pessoais
            coletados por meio desta plataforma, nos termos da Lei Geral de Protecao de Dados
            Pessoais (Lei n. 13.709/2018 — LGPD).
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">2. Dados Coletados</h2>
          <p>Coletamos os seguintes dados para prestacao do servico:</p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li><strong>Dados cadastrais:</strong> nome completo, e-mail, CNPJ da empresa, senha (armazenada com hash criptografico).</li>
            <li><strong>Dados fiscais:</strong> notas fiscais (XML NFS-e / NF-e) enviadas para validacao, resultados de validacao, findings e evidencias.</li>
            <li><strong>Dados de uso:</strong> logs de auditoria, historico de jobs, mensagens de chat com assistente fiscal.</li>
            <li><strong>Dados tecnicos:</strong> endereco IP, user-agent, timestamps de acesso.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">3. Finalidade do Tratamento</h2>
          <p>Seus dados sao tratados para as seguintes finalidades:</p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li>Prestacao do servico de validacao fiscal CBS/IBS conforme reforma tributaria (LC 214 + LC 227).</li>
            <li>Geracao de relatorios auditaveis e trilha de evidencias.</li>
            <li>Autenticacao e controle de acesso multi-tenant.</li>
            <li>Comunicacao sobre o servico e suporte tecnico.</li>
            <li>Cumprimento de obrigacoes legais e regulatorias.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">4. Base Legal (Art. 7, LGPD)</h2>
          <p>O tratamento de dados e realizado com base em:</p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li><strong>Consentimento (Art. 7, I):</strong> fornecido no momento do cadastro.</li>
            <li><strong>Execucao de contrato (Art. 7, V):</strong> necessario para prestacao do servico contratado.</li>
            <li><strong>Obrigacao legal (Art. 7, II):</strong> retencao de registros fiscais conforme legislacao tributaria.</li>
            <li><strong>Interesse legitimo (Art. 7, IX):</strong> seguranca da plataforma e prevencao a fraudes.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">5. Custodia de Dados Financeiros</h2>
          <p>
            Ao utilizar a plataforma Tribultz, voce nos confia dados financeiros e fiscais de sua
            empresa. Atuamos como <strong>custodiantes</strong> desses dados, aplicando:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li>Criptografia em transito (TLS/SSL) e em repouso.</li>
            <li>Isolamento multi-tenant — dados de cada empresa sao segregados logicamente.</li>
            <li>Checksums SHA-256 na trilha de auditoria para garantir integridade.</li>
            <li>Controle de acesso baseado em funcoes (RBAC).</li>
            <li>Backups regulares com retencao conforme politica de retencao fiscal.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">6. Compartilhamento de Dados</h2>
          <p>
            Nao compartilhamos seus dados pessoais ou fiscais com terceiros, exceto:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li>Provedores de infraestrutura (hospedagem em nuvem) sob acordo de confidencialidade.</li>
            <li>Determinacao judicial ou requisicao de autoridade competente.</li>
            <li>Com seu consentimento expresso para fins especificos.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">7. Seus Direitos (Art. 18, LGPD)</h2>
          <p>Voce tem direito a:</p>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            <li><strong>Acesso:</strong> solicitar copia de todos os seus dados pessoais.</li>
            <li><strong>Correcao:</strong> corrigir dados incompletos, inexatos ou desatualizados.</li>
            <li><strong>Anonimizacao/Eliminacao:</strong> solicitar exclusao de dados desnecessarios ou tratados em desconformidade.</li>
            <li><strong>Portabilidade:</strong> exportar seus dados em formato estruturado.</li>
            <li><strong>Revogacao do consentimento:</strong> retirar o consentimento a qualquer momento.</li>
            <li><strong>Informacao:</strong> saber com quem seus dados foram compartilhados.</li>
          </ul>
          <p className="mt-2">
            Para exercer seus direitos, acesse <strong>Configuracoes &gt; Meus Dados (LGPD)</strong> na
            plataforma ou entre em contato pelo e-mail: <strong>dpo@tribultz.com.br</strong>.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">8. Retencao de Dados</h2>
          <p>
            Dados fiscais sao retidos pelo periodo exigido pela legislacao tributaria brasileira
            (minimo 5 anos apos o exercicio fiscal). Dados cadastrais sao mantidos enquanto a conta
            estiver ativa. Apos solicitacao de exclusao, dados pessoais sao anonimizados, preservando
            registros fiscais conforme obrigacao legal.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">9. Seguranca</h2>
          <p>
            Adotamos medidas tecnicas e organizacionais para proteger seus dados, incluindo:
            criptografia, controle de acesso, monitoramento de seguranca (SOC), auditorias
            periodicas e treinamento da equipe.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">10. Encarregado de Dados (DPO)</h2>
          <p>
            Para questoes relacionadas a protecao de dados pessoais, entre em contato com nosso
            Encarregado de Dados (DPO): <strong>dpo@tribultz.com.br</strong>.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">11. Alteracoes</h2>
          <p>
            Esta politica pode ser atualizada periodicamente. Alteracoes significativas serao
            comunicadas por e-mail ou notificacao na plataforma.
          </p>
        </section>
      </div>
    </main>
  );
}
