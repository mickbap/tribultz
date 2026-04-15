import type { Metadata } from "next";
import { LegalPageLayout } from "@/components/legal/LegalPageLayout";

export const metadata: Metadata = {
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
        <h2 className="text-lg font-semibold text-slate-900">2. Tecnologias que usamos</h2>
        <p>
          A Tribultz usa uma combinação de cookies, armazenamento local do navegador e
          mecanismos técnicos de terceiros para manter a experiência funcional e segura.
        </p>
        <ul className="mt-3 list-disc space-y-2 pl-6">
          <li>
            <strong>Armazenamento local do navegador:</strong> o console grava chaves como
            tenant ativo, token de acesso, tipo de conta e lista de tenants
            para sustentar a navegação entre as ferramentas.
          </li>
          <li>
            <strong>Cookies essenciais de infraestrutura:</strong> provedores como Cloudflare
            e Vercel podem usar cookies técnicos e identificadores transitórios para
            roteamento, proteção da aplicação e estabilidade da sessão HTTP.
          </li>
          <li>
            <strong>Proteção antiautomação:</strong> quando o Turnstile estiver habilitado em
            cadastro, login ou recuperação de acesso, o navegador pode receber cookies ou
            sinais técnicos indispensáveis ao desafio antifraude.
          </li>
        </ul>
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
