export default function TermsPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-bold text-slate-900">Termos de Uso</h1>
      <p className="mt-2 text-sm text-slate-500">Última atualização: 29 de março de 2026</p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-slate-700">
        <section>
          <h2 className="text-lg font-semibold text-slate-900">1. Objeto</h2>
          <p>
            Estes Termos regulam o uso da plataforma Tribultz para validação fiscal,
            diagnóstico tributário, trilha auditável e operação de rotinas relacionadas
            a CBS, IBS e reforma tributária.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">2. Conta e acesso</h2>
          <p>
            O acesso ao console exige cadastro válido, informações verídicas e uso
            responsável das credenciais. Cada cliente é responsável pelas ações
            executadas por usuários autorizados em seu tenant.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">3. Uso permitido</h2>
          <p>
            A plataforma deve ser utilizada para fins lícitos, observando a legislação
            tributária, contratual e de proteção de dados aplicável. É vedado tentar
            violar segurança, engenharia reversa indevida ou uso que degrade o serviço.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">4. Responsabilidades</h2>
          <p>
            A Tribultz fornece infraestrutura, regras e evidências para apoiar a tomada
            de decisão fiscal. O cliente permanece responsável pela revisão final,
            parametrização do ERP e emissão de documentos fiscais em produção.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">5. Privacidade e dados</h2>
          <p>
            O tratamento de dados segue a Política de Privacidade da plataforma e a
            LGPD. Dados fiscais e operacionais são processados para prestação do serviço,
            segurança, auditoria e cumprimento de obrigações legais.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">6. Disponibilidade</h2>
          <p>
            A Tribultz busca alta disponibilidade, mas pode realizar manutenções,
            atualizações e correções emergenciais. Mudanças relevantes serão comunicadas
            pelos canais oficiais quando aplicável.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">7. Contato</h2>
          <p>
            Dúvidas comerciais, operacionais ou jurídicas podem ser encaminhadas para
            contato@tribultz.com.br.
          </p>
        </section>
      </div>
    </main>
  );
}
