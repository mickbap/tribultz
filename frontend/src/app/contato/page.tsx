/**
 * /contato — atendimento público, pré-login (#636).
 *
 * O rodapé público linkava "Suporte" para `/support`, que é página da ÁREA
 * LOGADA: client component que chama `apiFetch` para listar tickets, feedback e
 * erros conhecidos, sem navbar/rodapé públicos. O visitante deslogado carregava
 * 200 e via as chamadas autenticadas falharem — o "200 login-like" que o
 * diagnóstico externo registrou, e que o parecer inicial leu como "rota não
 * existe".
 *
 * Esta página é o destino público: canais reais, recuperação de acesso e o
 * caminho para a área logada de quem já é cliente. `/support` permanece
 * intacta para usuários autenticados.
 *
 * Sem promessa de SLA: a matriz comercial de atendimento (QA-14) é pendência de
 * Produto, e prometer prazo aqui seria inventar contrato.
 */

import type { Metadata } from "next";
import Link from "next/link";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { PublicFooter } from "@/components/public/PublicFooter";
import { WhatsAppLink } from "@/components/public/WhatsAppLink";

export const metadata: Metadata = {
  alternates: { canonical: "/contato" },
  title: "Contato e Suporte",
  description:
    "Fale com a Tribultz por e-mail ou WhatsApp, recupere o acesso à sua conta ou acesse o suporte técnico da área do cliente.",
};

const EMAIL = "contato@tribultz.com.br";
const DPO_EMAIL = "dpo@tribultz.com.br";
const WHATSAPP_HREF =
  "https://wa.me/5551991881026?text=Ol%C3%A1!%20Vim%20pelo%20site%20da%20Tribultz%20e%20quero%20falar%20com%20o%20atendimento.";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <div className="mt-3 space-y-2 text-sm leading-6 text-slate-700">{children}</div>
    </div>
  );
}

export default function ContatoPage() {
  return (
    <>
      <PublicNavbar />

      <main className="min-h-screen bg-slate-50">
        <section className="border-b border-slate-200 bg-white">
          <div className="mx-auto max-w-4xl px-6 py-14">
            <h1 className="text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
              Contato e suporte
            </h1>
            <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
              Fale com a gente sobre a plataforma, sobre a Reforma Tributária ou sobre
              a sua conta. Não é preciso ter cadastro.
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-4xl px-6 py-10">
          <div className="grid gap-5 md:grid-cols-2">
            <Card title="E-mail">
              <p>
                Dúvidas comerciais, técnicas ou sobre cobrança:{" "}
                <a href={`mailto:${EMAIL}`} className="font-medium text-tribultz-700 underline">
                  {EMAIL}
                </a>
              </p>
            </Card>

            <Card title="WhatsApp">
              <p>
                Atendimento pelo número{" "}
                <WhatsAppLink
                  href={WHATSAPP_HREF}
                  source="contato_publico"
                  className="font-medium text-tribultz-700 underline"
                >
                  (51) 99188-1026
                </WhatsAppLink>
                .
              </p>
            </Card>

            <Card title="Já é cliente?">
              <p>
                O suporte técnico com abertura de chamados fica na área do cliente, em{" "}
                <Link href="/support" className="font-medium text-tribultz-700 underline">
                  Suporte
                </Link>{" "}
                — é preciso estar autenticado.
              </p>
              <p>
                <Link href="/login" className="font-medium text-tribultz-700 underline">
                  Entrar na plataforma
                </Link>
              </p>
            </Card>

            <Card title="Perdeu o acesso?">
              <p>
                Redefina sua senha em{" "}
                <Link href="/forgot-password" className="font-medium text-tribultz-700 underline">
                  recuperação de senha
                </Link>
                . Se o e-mail de cadastro não estiver mais disponível, escreva para{" "}
                <a href={`mailto:${EMAIL}`} className="font-medium text-tribultz-700 underline">
                  {EMAIL}
                </a>
                .
              </p>
            </Card>

            <Card title="Privacidade e dados">
              <p>
                Encarregado de dados (LGPD):{" "}
                <a href={`mailto:${DPO_EMAIL}`} className="font-medium text-tribultz-700 underline">
                  {DPO_EMAIL}
                </a>
              </p>
              <p>
                Veja também a{" "}
                <Link href="/lgpd" className="font-medium text-tribultz-700 underline">
                  política de LGPD
                </Link>{" "}
                e a{" "}
                <Link href="/data-policy" className="font-medium text-tribultz-700 underline">
                  política de dados do diagnóstico gratuito
                </Link>
                .
              </p>
            </Card>

            <Card title="Quer testar antes de falar com alguém?">
              <p>
                O{" "}
                <Link href="/diagnostico" className="font-medium text-tribultz-700 underline">
                  diagnóstico gratuito
                </Link>{" "}
                valida um XML na hora, sem cadastro.
              </p>
            </Card>
          </div>
        </section>
      </main>

      <PublicFooter />
    </>
  );
}
