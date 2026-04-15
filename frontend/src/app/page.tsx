import type { Metadata } from "next";
import Link from "next/link";
import { PublicFooter } from "@/components/public/PublicFooter";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { NewsFeed } from "@/components/public/NewsFeed";

export const metadata: Metadata = {
  title: "Tribultz | Inteligência Fiscal para a Reforma Tributária",
  description:
    "Valide notas fiscais contra CBS/IBS, classifique produtos com cClassTrib e garanta conformidade com a LC 214. Motor determinístico com trilha auditável.",
};

// ── Dados estáticos ────────────────────────────────────────────────────────────

const painPoints = [
  {
    icon: "⚠",
    title: "NCM errado = crédito cancelado",
    description:
      "O CBS/IBS só é creditado se a classificação estiver correta. Um NCM divergente cancela o crédito do comprador automaticamente — sem aviso, sem recurso imediato.",
  },
  {
    icon: "⏱",
    title: "Validação manual não escala",
    description:
      "Uma empresa com 500 NFs/mês levaria 83h para verificar manualmente as 10 regras de conformidade da LC 214. Seu time fiscal não tem esse tempo.",
  },
  {
    icon: "📅",
    title: "O período educativo já terminou",
    description:
      "2026 foi o ano dos testes. A partir de 2027, CBS substitui PIS/COFINS com alíquota plena e penalidades em vigor. Cada nota não validada é risco acumulado.",
  },
];

const features = [
  {
    tag: "Calculadora pública",
    title: "CBS + IBS em 27 UFs. Sem cadastro.",
    description:
      "Informe NCM e valor base: receba alíquota exata CBS + IBS split UF/Município + XML snippet pronto para importar no seu ERP. Gratuito, ilimitado, sem conta.",
    cta: { label: "Calcular agora →", href: "/calculadora" },
    highlight: true,
  },
  {
    tag: "Motor determinístico",
    title: "10 regras LC 214 verificadas por nota.",
    description:
      "Upload do XML da NF-e: o motor verifica todas as regras da LC 214/LC 227 e retorna Findings com severidade ERROR / WARNING / INFO e base legal por regra.",
    cta: { label: "Validar NF-e →", href: "/validate-xml" },
    highlight: false,
  },
  {
    tag: "Evidência auditável",
    title: "Finding/Evidence v1.1. Defensável em fiscalização.",
    description:
      "Cada validação gera laudo estruturado com valor em risco, base legal e trilha auditável por nota. PDF assinado com hash SHA-256, pronto para responder autuações.",
    cta: { label: "Ver exemplo de relatório →", href: "/report" },
    highlight: false,
  },
  {
    tag: "Multi-CNPJ",
    title: "Para contadores: uma conta, toda a carteira.",
    description:
      "Workspace multi-tenant com isolamento por cliente. Gerencie conformidade CBS/IBS de todos os CNPJs em um único painel. Sem trocar de login, sem planilha de controle.",
    cta: { label: "Ver plano Contador →", href: "/pricing" },
    highlight: false,
  },
];

const metrics = [
  { value: "R$ 120 bi", label: "em contencioso PIS/COFINS + ICMS (2018–2023)" },
  { value: "98%", label: "de redução esperada em litígios após LC 214" },
  { value: "27", label: "UFs com alíquotas CBS/IBS no motor Tribultz" },
  { value: "10", label: "regras determinísticas verificadas por nota" },
];

const regimes = [
  {
    name: "MEI",
    impact: "Indireto",
    detail:
      "Custos de insumos variam com a reforma. Fornecedores no Simples podem ter crédito reduzido de CBS — o MEI absorve o repasse.",
    severity: "low",
  },
  {
    name: "Simples Nacional",
    impact: "Moderado",
    detail:
      "Separação de receitas e exceções por NCM exigem reclassificação do catálogo. Crédito CBS menor que no PIS/COFINS atual.",
    severity: "medium",
  },
  {
    name: "Lucro Presumido",
    impact: "Alto",
    detail:
      "Impacto não se resume a 'pagar mais ou menos'. Cada produto com NCM errado vira passivo fiscal. Reclassificação urgente.",
    severity: "high",
  },
  {
    name: "Lucro Real",
    impact: "Crítico",
    detail:
      "CBS/IBS ocupa o centro da gestão tributária. Split Payment, crédito por nota e conformidade de catálogo são requisitos operacionais diários.",
    severity: "critical",
  },
];

const steps = [
  {
    num: "01",
    title: "Upload ou NCM",
    description: "Faça upload do XML da NF-e ou informe NCM + valor base + UF de destino na calculadora.",
  },
  {
    num: "02",
    title: "Motor verifica em < 1s",
    description: "10 regras CBS/IBS checadas deterministicamente. Sem IA generativa, sem ambiguidade.",
  },
  {
    num: "03",
    title: "Evidência pronta",
    description: "PDF auditável + XML snippet para ERP + CSV para TOTVS/SAP. Defensável em qualquer fiscalização.",
  },
];

const severityColor: Record<string, string> = {
  low: "bg-emerald-50 border-emerald-200 text-emerald-800",
  medium: "bg-yellow-50 border-yellow-200 text-yellow-800",
  high: "bg-orange-50 border-orange-200 text-orange-800",
  critical: "bg-red-50 border-red-200 text-red-800",
};

const impactColor: Record<string, string> = {
  low: "text-emerald-700",
  medium: "text-yellow-700",
  high: "text-orange-700",
  critical: "text-red-700",
};

// ── Página ────────────────────────────────────────────────────────────────────

export default function HomePage() {
  return (
    <>
      <PublicNavbar />

      <main className="overflow-hidden">

        {/* ── HERO ────────────────────────────────────────────────────────── */}
        <section className="relative border-b border-slate-200">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(57,104,255,0.14),_transparent_36%),radial-gradient(circle_at_bottom_right,_rgba(16,185,129,0.12),_transparent_30%)]" />
          <div className="relative mx-auto grid max-w-6xl gap-12 px-4 py-20 md:grid-cols-[1.3fr_0.7fr] md:px-6 md:py-28">

            {/* Left */}
            <div>
              <span className="inline-flex rounded-full border border-tribultz-200 bg-white/80 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.22em] text-tribultz-700 backdrop-blur">
                Conformidade CBS/IBS · LC 214/2025
              </span>

              <h1 className="mt-6 max-w-2xl text-4xl font-black tracking-tight text-slate-950 md:text-5xl lg:text-6xl">
                Sua nota fiscal já está pronta para 2026?
              </h1>

              <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">
                Tribultz é o motor determinístico de validação CBS/IBS: 10 regras
                fiscais da LC 214, evidência auditável por nota e calculadora
                pública para as 27 UFs. Sem improviso, sem risco silencioso.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  href="/calculadora"
                  className="rounded-2xl bg-slate-950 px-7 py-3.5 text-center text-sm font-bold text-white shadow-lg shadow-slate-900/25 transition hover:bg-slate-800"
                >
                  Calcular CBS/IBS agora — grátis
                </Link>
                <Link
                  href="/register"
                  className="rounded-2xl border border-slate-300 bg-white px-7 py-3.5 text-center text-sm font-semibold text-slate-700 transition hover:border-tribultz-400 hover:text-tribultz-700"
                >
                  Criar conta gratuita
                </Link>
              </div>

              <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-xs font-medium text-slate-500">
                <span>✓ 27 UFs com alíquotas exatas</span>
                <span>✓ XML snippet para ERP incluso</span>
                <span>✓ Sem cadastro na calculadora</span>
                <span>✓ Evidência auditável em PDF</span>
              </div>
            </div>

            {/* Right — terminal card */}
            <div className="rounded-[2rem] border border-slate-200 bg-white/90 p-5 shadow-2xl shadow-slate-300/30 backdrop-blur md:self-start md:sticky md:top-8">
              <div className="rounded-[1.5rem] bg-slate-950 p-5 text-white font-mono text-sm">
                <p className="text-[10px] uppercase tracking-[0.22em] text-slate-400 mb-4">
                  Tribultz Motor · LC 214
                </p>
                <div className="space-y-3">
                  <div className="rounded-xl bg-white/8 px-4 py-3 border border-white/10">
                    <p className="text-[10px] text-slate-400 mb-1">NCM 02013000 · SP · R$ 1.000</p>
                    <p className="font-semibold text-emerald-400">✓ CBS R$ 88,00</p>
                    <p className="font-semibold text-emerald-400">✓ IBS R$ 177,00</p>
                  </div>
                  <div className="rounded-xl bg-white/8 px-4 py-3 border border-white/10">
                    <p className="text-[10px] text-slate-400 mb-1">Regra CBS-001 · alíquota</p>
                    <p className="font-semibold text-emerald-400">✓ PASS — 8,80% conforme</p>
                  </div>
                  <div className="rounded-xl bg-red-400/15 px-4 py-3 border border-red-300/20">
                    <p className="text-[10px] text-red-300 mb-1">Regra IBS-004 · CEST ausente</p>
                    <p className="font-semibold text-red-300">✗ ERROR — CEST obrigatório</p>
                    <p className="text-[10px] text-slate-400 mt-1">LC 214 art. 45 §2</p>
                  </div>
                  <div className="rounded-xl bg-emerald-400/12 px-4 py-3 border border-emerald-300/20">
                    <p className="text-[10px] text-emerald-200 mb-1">Evidência gerada</p>
                    <p className="text-xs text-emerald-100">PDF · XML · CSV/ERP · SHA-256</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── MÉTRICAS ────────────────────────────────────────────────────── */}
        <section className="border-b border-slate-100 bg-slate-50">
          <div className="mx-auto max-w-6xl px-4 py-10 md:px-6">
            <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
              {metrics.map((m) => (
                <div key={m.value} className="text-center">
                  <p className="text-3xl font-black text-slate-950 md:text-4xl">{m.value}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">{m.label}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── PROBLEMA ────────────────────────────────────────────────────── */}
        <section className="mx-auto max-w-6xl px-4 py-20 md:px-6">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-tribultz-700">
              O problema
            </p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
              Em 2026, toda nota fiscal tem CBS e IBS.{" "}
              <span className="text-slate-400">E a sua?</span>
            </h2>
            <p className="mt-4 text-base leading-7 text-slate-600">
              A reforma tributária não espera. O período educativo é real, mas
              temporário. Cada nota com classificação errada acumula risco de
              crédito perdido, autuação e contencioso.
            </p>
          </div>

          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {painPoints.map((p) => (
              <article
                key={p.title}
                className="rounded-[1.75rem] border border-slate-200 bg-white p-7 shadow-sm"
              >
                <span className="text-2xl">{p.icon}</span>
                <h3 className="mt-4 text-lg font-semibold text-slate-900">{p.title}</h3>
                <p className="mt-3 text-sm leading-7 text-slate-600">{p.description}</p>
              </article>
            ))}
          </div>
        </section>

        {/* ── SOLUÇÃO / FEATURES ──────────────────────────────────────────── */}
        <section className="border-y border-slate-200 bg-slate-50">
          <div className="mx-auto max-w-6xl px-4 py-20 md:px-6">
            <div className="max-w-2xl">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-tribultz-700">
                A solução
              </p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
                Motor determinístico.{" "}
                <span className="text-slate-400">Evidência auditável. Zero interpretação.</span>
              </h2>
              <p className="mt-4 text-base leading-7 text-slate-600">
                Sem IA generativa inventando alíquotas. Cada resultado tem base
                legal, valor calculado e evidência exportável. Do XML ao PDF em
                menos de 1 segundo.
              </p>
            </div>

            <div className="mt-12 grid gap-6 md:grid-cols-2">
              {features.map((f) => (
                <article
                  key={f.title}
                  className={`rounded-[2rem] border p-8 ${
                    f.highlight
                      ? "border-tribultz-200 bg-tribultz-50 shadow-md shadow-tribultz-100/50"
                      : "border-slate-200 bg-white shadow-sm"
                  }`}
                >
                  <span className="inline-block rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-tribultz-700">
                    {f.tag}
                  </span>
                  <h3 className="mt-4 text-xl font-bold text-slate-900">{f.title}</h3>
                  <p className="mt-3 text-sm leading-7 text-slate-600">{f.description}</p>
                  <Link
                    href={f.cta.href}
                    className="mt-5 inline-block text-sm font-semibold text-tribultz-700 transition hover:text-tribultz-900"
                  >
                    {f.cta.label}
                  </Link>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ── COMO FUNCIONA ───────────────────────────────────────────────── */}
        <section className="mx-auto max-w-6xl px-4 py-20 md:px-6">
          <div className="max-w-xl">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-tribultz-700">
              Como funciona
            </p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
              Do XML à evidência em 3 passos.
            </h2>
          </div>

          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {steps.map((s) => (
              <div key={s.num} className="flex gap-5">
                <span className="mt-0.5 shrink-0 text-4xl font-black text-slate-200">
                  {s.num}
                </span>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">{s.title}</h3>
                  <p className="mt-2 text-sm leading-7 text-slate-600">{s.description}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-12 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/calculadora"
              className="rounded-2xl bg-slate-950 px-7 py-3.5 text-center text-sm font-bold text-white shadow-lg shadow-slate-900/20 transition hover:bg-slate-800"
            >
              Testar a calculadora agora
            </Link>
            <Link
              href="/validate-xml"
              className="rounded-2xl border border-slate-300 bg-white px-7 py-3.5 text-center text-sm font-semibold text-slate-700 transition hover:border-tribultz-400 hover:text-tribultz-700"
            >
              Validar minha NF-e
            </Link>
          </div>
        </section>

        {/* ── IMPACTO POR REGIME ──────────────────────────────────────────── */}
        <section className="border-y border-slate-200 bg-white">
          <div className="mx-auto max-w-6xl px-4 py-20 md:px-6">
            <div className="max-w-2xl">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-tribultz-700">
                Impacto por regime
              </p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
                Cada regime tem exposição diferente.{" "}
                <span className="text-slate-400">Qual é o seu?</span>
              </h2>
              <p className="mt-4 text-sm leading-7 text-slate-600">
                O impacto da reforma nunca se resume a "pagar mais ou menos". Depende
                do regime, do catálogo e da precisão das classificações fiscais.
              </p>
            </div>

            <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {regimes.map((r) => (
                <div
                  key={r.name}
                  className={`rounded-[1.75rem] border p-6 ${severityColor[r.severity]}`}
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    {r.name}
                  </p>
                  <p className={`mt-2 text-xl font-black ${impactColor[r.severity]}`}>
                    {r.impact}
                  </p>
                  <p className="mt-3 text-xs leading-6 text-slate-600">{r.detail}</p>
                </div>
              ))}
            </div>

            <p className="mt-8 text-sm text-slate-500">
              Não sabe qual é a exposição específica da sua empresa?{" "}
              <Link href="/diagnostico" className="font-semibold text-tribultz-700 hover:underline">
                Rode o diagnóstico gratuito →
              </Link>
            </p>
          </div>
        </section>

        {/* ── NEWS / CHANGELOG ────────────────────────────────────────────── */}
        <section className="mx-auto max-w-6xl px-4 py-16 md:px-6">
          <div className="flex items-end justify-between gap-6">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-tribultz-700">
                Atualizações
              </p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-950">
                Motor sempre atualizado com a legislação.
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-7 text-slate-600">
                Cada alteração na LC 214, NT 2025.002 ou tabela de alíquotas entra
                no motor imediatamente. Você não precisa acompanhar o DOU.
              </p>
            </div>
            <Link
              href="/changelog"
              className="shrink-0 text-sm font-semibold text-tribultz-700 transition hover:text-tribultz-800"
            >
              Ver changelog →
            </Link>
          </div>
          <div className="mt-8">
            <NewsFeed limit={3} compact />
          </div>
        </section>

        {/* ── CTA FINAL ───────────────────────────────────────────────────── */}
        <section className="mx-auto max-w-6xl px-4 pb-20 md:px-6">
          <div className="rounded-[2rem] bg-slate-950 px-8 py-12 text-white md:px-12">
            <div className="flex flex-col gap-8 md:flex-row md:items-center md:justify-between">
              <div className="max-w-xl">
                <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Comece agora
                </p>
                <h2 className="mt-3 text-3xl font-bold tracking-tight md:text-4xl">
                  Sua NF precisa ser CBS/IBS compliant.{" "}
                  <span className="text-emerald-400">Confirme isso hoje.</span>
                </h2>
                <p className="mt-4 text-sm leading-7 text-slate-300">
                  Calculadora gratuita sem cadastro. Conta gratuita para até 5
                  validações de NF-e por mês. Sem cartão de crédito.
                </p>
              </div>
              <div className="flex shrink-0 flex-col gap-3 sm:flex-row md:flex-col lg:flex-row">
                <Link
                  href="/calculadora"
                  className="rounded-2xl bg-emerald-400 px-7 py-3.5 text-center text-sm font-bold text-slate-950 transition hover:bg-emerald-300"
                >
                  Abrir calculadora
                </Link>
                <Link
                  href="/register"
                  className="rounded-2xl border border-white/20 px-7 py-3.5 text-center text-sm font-semibold text-white transition hover:border-white/50"
                >
                  Criar conta grátis
                </Link>
              </div>
            </div>

            <div className="mt-10 grid grid-cols-2 gap-4 border-t border-white/10 pt-8 md:grid-cols-4">
              {[
                "Calculadora 27 UFs gratuita",
                "5 validações/mês no plano free",
                "Sem cartão de crédito",
                "Cancel a qualquer momento",
              ].map((item) => (
                <p key={item} className="text-xs text-slate-400">
                  <span className="mr-1 text-emerald-400">✓</span>
                  {item}
                </p>
              ))}
            </div>
          </div>
        </section>

        {/* LGPD Declaration */}
        <section className="border-t border-slate-200 bg-slate-50">
          <div className="mx-auto max-w-4xl px-4 py-8 md:px-6">
            <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100">
                    <span className="text-lg">🔒</span>
                  </div>
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-slate-900 mb-2">
                    Lei Geral de Proteção de Dados (LGPD)
                  </h3>
                  <p className="text-sm text-slate-600 mb-4">
                    Tratamos dados pessoais e operacionais com segurança, transparência e escopo mínimo
                    necessário para executar o serviço. A homepage, a calculadora, o diagnóstico e o
                    console seguem políticas consistentes de privacidade, cookies e LGPD, com trilha de
                    auditoria, isolamento por tenant e canal direto para exercício de direitos.
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <Link
                      href="/lgpd"
                      className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                    >
                      Saiba mais sobre LGPD →
                    </Link>
                    <Link
                      href="/privacy"
                      className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                    >
                      Política de Privacidade
                    </Link>
                    <Link
                      href="/cookies"
                      className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                    >
                      Política de Cookies
                    </Link>
                    <Link
                      href="/terms"
                      className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                    >
                      Termos de Uso
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

      </main>

      <PublicFooter />
    </>
  );
}
