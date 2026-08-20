import type { Metadata } from "next";
import { LegalPageLayout } from "@/components/legal/LegalPageLayout";

export const metadata: Metadata = {
  alternates: { canonical: "/terms" },
  title: "Termos de Uso",
  description: "Termos de uso da plataforma Tribultz de conformidade fiscal.",
};

export default function TermsPage() {
  return (
    <LegalPageLayout
      title="Termos de Uso"
      updatedAt="10 de abril de 2026"
      summary="Estes termos disciplinam o uso da homepage, calculadora, diagnóstico, console autenticado e demais ferramentas Tribultz voltadas à operação fiscal e à reforma tributária."
    >
      <section>
        <h2 className="text-lg font-semibold text-slate-900">1. Objeto</h2>
        <p>
          A Tribultz fornece ferramentas para validação fiscal, diagnóstico, cálculo CBS/IBS,
          auditoria, evidências, relatórios e apoio à rotina tributária. O produto combina
          automação determinística, trilha auditável e serviços complementares de operação.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">2. Ferramentas públicas e console</h2>
        <p>
          Parte da experiência pode ser acessada sem cadastro, como a homepage, a calculadora e
          alguns fluxos públicos. Funcionalidades completas de validação, relatórios, auditoria,
          histórico, billing e memória dependem de conta válida, plano compatível e uso regular.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">3. Uso permitido</h2>
        <ul className="mt-3 list-disc space-y-2 pl-6">
          <li>Utilizar a plataforma para fins lícitos e compatíveis com a legislação aplicável.</li>
          <li>Manter dados cadastrais corretos e proteger credenciais de acesso.</li>
          <li>Não degradar, testar carga de forma abusiva ou tentar contornar mecanismos de segurança.</li>
          <li>Não utilizar o serviço para engenharia reversa indevida, fraude ou acesso não autorizado.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">4. Responsabilidades do cliente</h2>
        <p>
          O cliente continua responsável pela revisão final de parâmetros fiscais, pela decisão
          operacional sobre emissão de documentos e pela conferência do ERP, mesmo quando utilizar
          automação, relatórios ou evidências técnicas geradas pelo Tribultz.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">5. Disponibilidade e evolução do produto</h2>
        <p>
          Buscamos alta disponibilidade, mas o serviço pode passar por manutenção, atualizações,
          correções emergenciais, evolução de integrações e ajustes de segurança. Quando fizer sentido
          operacionalmente, mudanças relevantes serão comunicadas pelos canais oficiais.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">6. Cobrança e terceiros</h2>
        <p>
          Assinaturas, PIX, checkout e eventos de cobrança podem ser operados por parceiros
          especializados. O uso desses fluxos também depende das regras e limitações técnicas
          desses provedores.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">7. Privacidade e LGPD</h2>
        <p>
          O tratamento de dados pessoais e operacionais segue a Política de Privacidade, a Política
          de Cookies e as diretrizes de LGPD publicadas pela Tribultz. Ao usar a plataforma, o usuário
          concorda com essas políticas complementares.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">8. Contato</h2>
        <p>
          Dúvidas comerciais, operacionais ou jurídicas podem ser encaminhadas para
          <strong> contato@tribultz.com.br</strong>.
        </p>
      </section>
    </LegalPageLayout>
  );
}
