export default function TermsPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-bold text-slate-900">Termos de Uso</h1>
      <p className="mt-2 text-sm text-slate-500">Ultima atualizacao: 29 de marco de 2026</p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-slate-700">
        <section>
          <h2 className="text-lg font-semibold text-slate-900">1. Objeto</h2>
          <p>
            Estes Termos regulam o uso da plataforma Tribultz para validacao fiscal,
            diagnostico tributario, trilha auditavel e operacao de rotinas relacionadas
            a CBS, IBS e reforma tributaria.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">2. Conta e acesso</h2>
          <p>
            O acesso ao console exige cadastro valido, informacoes veridicas e uso
            responsavel das credenciais. Cada cliente e responsavel pelas acoes
            executadas por usuarios autorizados em seu tenant.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">3. Uso permitido</h2>
          <p>
            A plataforma deve ser utilizada para fins licitos, observando a legislacao
            tributaria, contratual e de protecao de dados aplicavel. E vedado tentar
            violar seguranca, engenharia reversa indevida ou uso que degrade o servico.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">4. Responsabilidades</h2>
          <p>
            A Tribultz fornece infraestrutura, regras e evidencias para apoiar a tomada
            de decisao fiscal. O cliente permanece responsavel pela revisao final,
            parametrizacao do ERP e emissao de documentos fiscais em producao.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">5. Privacidade e dados</h2>
          <p>
            O tratamento de dados segue a Politica de Privacidade da plataforma e a
            LGPD. Dados fiscais e operacionais sao processados para prestacao do servico,
            seguranca, auditoria e cumprimento de obrigacoes legais.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">6. Disponibilidade</h2>
          <p>
            A Tribultz busca alta disponibilidade, mas pode realizar manutencoes,
            atualizacoes e correcoes emergenciais. Mudancas relevantes serao comunicadas
            pelos canais oficiais quando aplicavel.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-900">7. Contato</h2>
          <p>
            Duvidas comerciais, operacionais ou juridicas podem ser encaminhadas para
            contato@tribultz.com.br.
          </p>
        </section>
      </div>
    </main>
  );
}
