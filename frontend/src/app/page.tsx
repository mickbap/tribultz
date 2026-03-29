import Link from "next/link";
import { PublicFooter } from "@/components/public/PublicFooter";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { NewsFeed } from "@/components/public/NewsFeed";

const highlights = [
  {
    title: "Memoria de precedentes",
    description:
      "Cada validacao acumula contexto operacional para acelerar decisoes fiscais com consistencia.",
  },
  {
    title: "Cloud soberana",
    description:
      "Arquitetura preparada para operacao no Brasil, com governanca, trilha de auditoria e isolamento por tenant.",
  },
  {
    title: "Determinismo operacional",
    description:
      "Regras explicaveis, evidencias auditaveis e menos dependencia de interpretacao manual na rotina tributaria.",
  },
];

export default function HomePage() {
  return (
    <>
      <PublicNavbar />

      <main className="overflow-hidden">
        <section className="relative border-b border-slate-200">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(57,104,255,0.16),_transparent_34%),radial-gradient(circle_at_bottom_right,_rgba(16,185,129,0.14),_transparent_28%)]" />
          <div className="relative mx-auto grid max-w-6xl gap-10 px-4 py-20 md:grid-cols-[1.2fr_0.8fr] md:px-6 md:py-28">
            <div>
              <span className="inline-flex rounded-full border border-tribultz-200 bg-white/80 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.24em] text-tribultz-700 backdrop-blur">
                Marketing Phase M04
              </span>
              <h1 className="mt-6 max-w-4xl text-4xl font-black tracking-tight text-slate-950 md:text-6xl">
                Inteligencia Fiscal Deterministica com Memoria de Precedentes
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600 md:text-xl">
                A Tribultz transforma a reforma tributaria em operacao confiavel:
                regras explicaveis, contexto historico e execucao preparada para
                times que precisam responder rapido sem abrir mao de governanca.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  href="/register"
                  className="rounded-2xl bg-slate-950 px-6 py-3 text-center text-sm font-semibold text-white shadow-lg shadow-slate-900/20 transition hover:bg-slate-800"
                >
                  Criar conta gratuita
                </Link>
                <Link
                  href="/diagnostico"
                  className="rounded-2xl border border-slate-300 bg-white px-6 py-3 text-center text-sm font-semibold text-slate-700 transition hover:border-tribultz-400 hover:text-tribultz-700"
                >
                  Rodar diagnostico gratuito
                </Link>
              </div>
              <div className="mt-10 flex flex-wrap gap-6 text-sm text-slate-500">
                <span>IA fiscal com trilha auditavel</span>
                <span>Memoria aplicada a precedentes</span>
                <span>Pronto para CBS, IBS e operacao multi-CNPJ</span>
              </div>
            </div>

            <div className="rounded-[2rem] border border-slate-200 bg-white/90 p-6 shadow-2xl shadow-slate-300/30 backdrop-blur">
              <div className="rounded-[1.5rem] bg-slate-950 p-6 text-white">
                <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
                  Tribultz Signal
                </p>
                <p className="mt-4 text-2xl font-bold">
                  Seu time fiscal decide com contexto, nao com improviso.
                </p>
                <div className="mt-6 grid gap-3">
                  <div className="rounded-2xl bg-white/10 p-4">
                    <p className="text-xs text-slate-300">Camada 1</p>
                    <p className="mt-1 font-semibold">Motor deterministico de validacao</p>
                  </div>
                  <div className="rounded-2xl bg-white/10 p-4">
                    <p className="text-xs text-slate-300">Camada 2</p>
                    <p className="mt-1 font-semibold">Memoria de precedentes e evidencias</p>
                  </div>
                  <div className="rounded-2xl bg-emerald-400/15 p-4 ring-1 ring-emerald-300/30">
                    <p className="text-xs text-emerald-100">Camada 3</p>
                    <p className="mt-1 font-semibold text-emerald-50">
                      Decisao fiscal pronta para auditoria e execucao
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-16 md:px-6">
          <div className="flex items-end justify-between gap-6">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-tribultz-700">
                Produto
              </p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-950">
                O que entra no ar com a Home
              </h2>
            </div>
          </div>
          <div className="mt-8 grid gap-5 md:grid-cols-3">
            {highlights.map((item) => (
              <article
                key={item.title}
                className="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/70"
              >
                <h3 className="text-xl font-semibold text-slate-900">{item.title}</h3>
                <p className="mt-3 text-sm leading-7 text-slate-600">{item.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="border-y border-slate-200 bg-white/70">
          <div className="mx-auto max-w-6xl px-4 py-16 md:px-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.18em] text-tribultz-700">
                  News
                </p>
                <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-950">
                  Ultimas atualizacoes do produto
                </h2>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
                  Este bloco consome o endpoint publico de novidades do backend para
                  manter a Home alinhada com o que acabou de entrar em producao.
                </p>
              </div>
              <Link
                href="/changelog"
                className="text-sm font-semibold text-tribultz-700 transition hover:text-tribultz-800"
              >
                Ver changelog completo
              </Link>
            </div>
            <div className="mt-8">
              <NewsFeed limit={3} compact />
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-16 md:px-6">
          <div className="rounded-[2rem] bg-slate-950 px-6 py-10 text-white md:px-10">
            <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Go-live
                </p>
                <h2 className="mt-3 text-3xl font-bold tracking-tight">
                  Tribultz pronta para captar demanda organica com uma Home publica.
                </h2>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row">
                <Link
                  href="/pricing"
                  className="rounded-2xl bg-white px-6 py-3 text-center text-sm font-semibold text-slate-950 transition hover:bg-slate-100"
                >
                  Ver planos
                </Link>
                <Link
                  href="/login"
                  className="rounded-2xl border border-white/20 px-6 py-3 text-center text-sm font-semibold text-white transition hover:border-white/40"
                >
                  Entrar no console
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <PublicFooter />
    </>
  );
}
