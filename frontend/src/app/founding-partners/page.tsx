import type { Metadata } from "next";
import Link from "next/link";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { PublicFooter } from "@/components/public/PublicFooter";

// Formulário oficial de inscrição do Programa Founding Partners.
const FORM_URL = "https://forms.office.com/r/Cf6yK6kqsA";

export const metadata: Metadata = {
  title: "Programa Founding Partners — construa a Tribultz conosco",
  description:
    "A Tribultz está formando um grupo seleto de empresas para construir a plataforma durante a Reforma Tributária. Não é um teste de software — é construção conjunta. Veja como participar.",
  openGraph: {
    title: "Programa Founding Partners — Tribultz",
    description:
      "Construa a primeira geração da Tribultz junto de quem vive a Reforma Tributária. Programa de construção conjunta — inscrições abertas.",
    type: "website",
  },
};

const JOURNEY: { step: string; label: string; desc: string }[] = [
  { step: "01", label: "Inscrição", desc: "Você preenche o formulário do Programa." },
  { step: "02", label: "Aprovação", desc: "Analisamos o perfil e o momento fiscal da empresa." },
  { step: "03", label: "Convite", desc: "Enviamos o convite oficial de participação." },
  { step: "04", label: "Primeiro acesso", desc: "Você entra na plataforma e configura a conta." },
  { step: "05", label: "Envio da amostra", desc: "Você envia documentos fiscais reais da operação." },
  { step: "06", label: "Apresentação do TERA", desc: "Mostramos o diagnóstico técnico sobre seus documentos." },
  { step: "07", label: "Uso da plataforma", desc: "Você opera a Tribultz no dia a dia e ajuda a evoluí-la." },
];

const AUDIENCE: string[] = [
  "Escritórios de contabilidade",
  "Departamentos fiscais",
  "Consultorias tributárias",
  "Empresas emissoras de documentos fiscais",
  "Especialistas tributários",
  "Empresas de tecnologia",
  "ERPs",
  "Entidades empresariais",
];

const BENEFITS: { title: string; desc: string }[] = [
  { title: "Acesso antecipado", desc: "Use a plataforma antes do mercado, durante a implantação da Reforma." },
  { title: "Acompanhamento próximo", desc: "Contato direto com o time que constrói a Tribultz." },
  { title: "TERA", desc: "Diagnóstico técnico sobre os seus próprios documentos fiscais." },
  { title: "Participação ativa", desc: "Sua operação real orienta a evolução da plataforma." },
];

export default function FoundingPartnersPage() {
  return (
    <div className="bg-white">
      <PublicNavbar />
      <main>
        {/* HERO */}
        <section className="border-b border-slate-200 bg-gradient-to-b from-[#F4F7FF] to-white">
          <div className="mx-auto max-w-6xl px-4 py-20 md:px-6 md:py-28">
            <span className="inline-block rounded-full bg-[#2956E3]/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-[#2956E3]">
              Programa Founding Partners
            </span>
            <h1 className="mt-4 max-w-3xl text-4xl font-extrabold leading-tight tracking-tight text-[#24292E] md:text-5xl">
              Construa a Tribultz conosco
            </h1>
            <p className="mt-5 max-w-2xl text-lg text-slate-600">
              A Tribultz está formando um grupo seleto de empresas para participar da evolução da
              plataforma durante a implantação da Reforma Tributária. O objetivo não é testar
              software — é construir uma plataforma melhor junto de quem vive esse cenário todos os dias.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <a
                href={FORM_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg bg-[#2956E3] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#2044C7]"
                style={{ boxShadow: "0 8px 24px rgba(41,86,227,0.20)" }}
              >
                Quero participar do Programa Founding Partners
              </a>
              <a href="#como-funciona" className="text-sm font-medium text-[#2956E3] hover:underline">
                Ver como funciona ↓
              </a>
            </div>
          </div>
        </section>

        {/* O QUE É */}
        <section className="py-20 md:py-24">
          <div className="mx-auto max-w-3xl px-4 md:px-6">
            <h2 className="text-3xl font-extrabold tracking-tight text-[#24292E]">O que é o Programa</h2>
            <div className="mt-5 space-y-4 text-lg text-slate-600">
              <p>
                O Programa Founding Partners existe para aproximar a Tribultz das empresas que vivem
                a Reforma Tributária diariamente — permitindo que a evolução da plataforma seja
                guiada por <strong className="text-[#24292E]">operações reais</strong>, não por
                hipóteses internas.
              </p>
              <p>
                Não é um programa de testes. É um programa de{" "}
                <strong className="text-[#24292E]">construção conjunta</strong>: os Founding Partners
                ajudam a moldar a primeira geração da plataforma, com acesso próximo ao time e
                influência direta sobre o que é construído.
              </p>
            </div>
          </div>
        </section>

        {/* COMO FUNCIONA */}
        <section id="como-funciona" className="border-y border-slate-200 bg-[#F8FAFC] py-20 md:py-24">
          <div className="mx-auto max-w-6xl px-4 md:px-6">
            <h2 className="text-3xl font-extrabold tracking-tight text-[#24292E]">Como funciona</h2>
            <p className="mt-3 max-w-2xl text-slate-600">Da inscrição ao uso diário da plataforma — uma jornada acompanhada de perto.</p>
            <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {JOURNEY.map((j) => (
                <li key={j.step} className="rounded-xl border border-slate-200 bg-white p-5">
                  <span className="font-mono text-sm font-bold text-[#2956E3]">{j.step}</span>
                  <h3 className="mt-1 text-lg font-bold text-[#24292E]">{j.label}</h3>
                  <p className="mt-1 text-sm text-slate-600">{j.desc}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* PARA QUEM É */}
        <section className="py-20 md:py-24">
          <div className="mx-auto max-w-6xl px-4 md:px-6">
            <h2 className="text-3xl font-extrabold tracking-tight text-[#24292E]">Para quem é</h2>
            <p className="mt-3 max-w-2xl text-slate-600">Perfis que vivem a operação fiscal e a Reforma de perto.</p>
            <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {AUDIENCE.map((a) => (
                <div key={a} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
                  <span className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-[#2956E3]/10 text-[#2956E3]" aria-hidden="true">
                    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M4 12.5l5 5L20 6" /></svg>
                  </span>
                  <span className="text-sm font-medium text-[#24292E]">{a}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* BENEFÍCIOS */}
        <section className="border-y border-slate-200 bg-[#F8FAFC] py-20 md:py-24">
          <div className="mx-auto max-w-6xl px-4 md:px-6">
            <h2 className="text-3xl font-extrabold tracking-tight text-[#24292E]">Benefícios</h2>
            <p className="mt-3 max-w-2xl text-slate-600">Participação, proximidade e evidência técnica — sem promessas comerciais.</p>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {BENEFITS.map((b) => (
                <div key={b.title} className="rounded-xl border border-slate-200 bg-white p-5">
                  <h3 className="text-lg font-bold text-[#24292E]">{b.title}</h3>
                  <p className="mt-1 text-sm text-slate-600">{b.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA FINAL */}
        <section className="py-20 md:py-24">
          <div className="mx-auto max-w-4xl px-4 text-center md:px-6">
            <h2 className="text-3xl font-extrabold tracking-tight text-[#24292E] md:text-4xl">
              Faça parte da construção da Tribultz
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-600">
              Inscreva sua empresa no Programa Founding Partners. Analisamos cada inscrição e
              enviamos o convite para os perfis selecionados.
            </p>
            <a
              href={FORM_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-8 inline-block rounded-lg bg-[#2956E3] px-8 py-3.5 text-sm font-semibold text-white transition-colors hover:bg-[#2044C7]"
              style={{ boxShadow: "0 8px 24px rgba(41,86,227,0.20)" }}
            >
              Quero participar do Programa Founding Partners
            </a>
          </div>
        </section>
      </main>
      <PublicFooter />
    </div>
  );
}
