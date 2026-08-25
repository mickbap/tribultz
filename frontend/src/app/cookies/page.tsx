import type { Metadata } from "next";
import { LegalPageLayout } from "@/components/legal/LegalPageLayout";

export const metadata: Metadata = {
  alternates: { canonical: "/cookies" },
  title: "Cookies",
  description: "Política de cookies da plataforma Tribultz.",
};

export default function CookiesPage() {
  return (
    <LegalPageLayout
      title="Política de Cookies"
      updatedAt="10 de abril de 2026"
      summary="Explicamos como a Tribultz usa cookies e tecnologias equivalentes para manter a plataforma segura, lembrar preferências e sustentar fluxos essenciais do produto."
    >
      <section>
        <h2 className="text-lg font-semibold text-slate-900">1. Escopo</h2>
        <p>
          Esta política se aplica à homepage pública, à calculadora, ao diagnóstico,
          ao console autenticado e às demais ferramentas Tribultz disponíveis em
          <strong> tribultz.com.br</strong>.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">2. Inventário</h2>
        <p>
          A Tribultz <strong>não define cookies próprios</strong>. O que sustenta a sessão
          fica em armazenamento local do navegador — tecnologia equivalente a cookie para
          fins da LGPD, por isso listada aqui com o mesmo detalhe.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[42rem] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-300 text-slate-900">
                <th className="py-2 pr-4 font-semibold">Nome</th>
                <th className="py-2 pr-4 font-semibold">Categoria</th>
                <th className="py-2 pr-4 font-semibold">Finalidade</th>
                <th className="py-2 pr-4 font-semibold">Duração</th>
                <th className="py-2 font-semibold">Origem</th>
              </tr>
            </thead>
            <tbody className="align-top">
              <tr className="border-b border-slate-200">
                <td className="py-2 pr-4">
                  <code>tribultz-token</code>, <code>tribultz-tenant</code> e chaves de
                  conta <em>(armazenamento local, não cookie)</em>
                </td>
                <td className="py-2 pr-4">Estritamente necessário</td>
                <td className="py-2 pr-4">
                  Manter a sessão autenticada e a empresa ativa entre as telas.
                </td>
                <td className="py-2 pr-4">Até você sair da conta ou limpar o navegador</td>
                <td className="py-2">Tribultz (primeira parte)</td>
              </tr>
              <tr className="border-b border-slate-200">
                <td className="py-2 pr-4">
                  <code>tribultz-cookie-consent</code> <em>(armazenamento local)</em>
                </td>
                <td className="py-2 pr-4">Estritamente necessário</td>
                <td className="py-2 pr-4">
                  Registrar a sua escolha de cookies e a versão desta política sob a qual
                  ela foi feita — é o que evita perguntarmos de novo a cada visita.
                </td>
                <td className="py-2 pr-4">Até você revogar ou limpar o navegador</td>
                <td className="py-2">Tribultz (primeira parte)</td>
              </tr>
              <tr className="border-b border-slate-200">
                <td className="py-2 pr-4">Token do Cloudflare Turnstile</td>
                <td className="py-2 pr-4">Estritamente necessário</td>
                <td className="py-2 pr-4">
                  Distinguir pessoa de automação em cadastro e login. Por padrão o
                  Turnstile emite um token de uso único, não um cookie.
                </td>
                <td className="py-2 pr-4">Uso único, expira ao ser validado</td>
                <td className="py-2">Cloudflare (terceiro)</td>
              </tr>
              <tr className="border-b border-slate-200">
                <td className="py-2 pr-4">
                  <code>_ga</code>, <code>_ga_&lt;ID&gt;</code>
                </td>
                <td className="py-2 pr-4">
                  Análise de audiência — <strong>só com o seu consentimento</strong>
                </td>
                <td className="py-2 pr-4">
                  Medir uso agregado das páginas para orientar melhorias. Não formam perfil
                  comportamental nem alimentam publicidade.
                </td>
                <td className="py-2 pr-4">Até 2 anos (padrão do Google)</td>
                <td className="py-2">Google Analytics 4 (terceiro)</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm text-slate-600">
          Verificamos em 20/08/2026 que as rotas públicas não recebem cookie definido pelo
          servidor. Provedores de infraestrutura (Cloudflare, Vercel) podem definir cookies
          técnicos transitórios de roteamento e proteção; quando ocorrem, são estritamente
          necessários e não servem a publicidade.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">3. O que não usamos hoje</h2>
        <ul className="mt-3 list-disc space-y-2 pl-6">
          <li>A aplicação não depende de cookies próprios de publicidade comportamental.</li>
          <li>Não vendemos dados de navegação a terceiros.</li>
          <li>
            Se ferramentas de analytics, remarketing ou experimentação exigirem consentimento
            adicional no futuro, esta política e a experiência de coleta serão atualizadas.
          </li>
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">4. Base legal e finalidade</h2>
        <p>
          Os mecanismos essenciais são utilizados para executar o serviço, proteger a conta,
          prevenir abuso, manter preferências operacionais e garantir a disponibilidade das
          ferramentas. Quando aplicável, o tratamento segue execução contratual, obrigação
          legal, legítimo interesse e medidas de segurança compatíveis com a LGPD.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">5. Como gerenciar</h2>
        <p>
          Você pode limpar cookies e armazenamento local diretamente no navegador. Ao fazer isso,
          parte da experiência pode ser reiniciada, incluindo tenant ativo, preferências e sessão
          do console.
        </p>
        <p className="mt-2">
          Se o bloqueio de cookies essenciais impedir login, cadastro ou fluxos protegidos por
          antiautomação, a plataforma pode deixar de funcionar corretamente até a reativação
          desses mecanismos.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">6. Contato</h2>
        <p>
          Para dúvidas sobre privacidade, cookies ou exercício de direitos, fale com o DPO em
          <strong> dpo@tribultz.com.br</strong> ou consulte a página de <strong>LGPD</strong>.
        </p>
      </section>
    </LegalPageLayout>
  );
}
