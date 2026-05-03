import type { Metadata } from "next";
import Link from "next/link";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { PublicFooter } from "@/components/public/PublicFooter";
import { NewsFeed } from "@/components/public/NewsFeed";

export const metadata: Metadata = {
  title: "Tribultz — Validação CBS/IBS e Compliance para a Reforma Tributária | LC 214",
  description:
    "Valide notas fiscais contra CBS e IBS da reforma tributária brasileira (LC 214). Motor determinístico com 18 regras, SPED Fiscal, Compliance Score e exportação para TOTVS, SAP, Omie e Linx.",
  keywords: [
    "CBS", "IBS", "reforma tributária", "LC 214", "LC 227",
    "validação fiscal", "SPED fiscal", "nota fiscal eletrônica", "NFe CBS IBS",
    "calculadora CBS IBS", "compliance tributário", "Split Payment",
    "cClassTrib", "NCM", "CEST", "reforma tributária 2026",
  ],
  alternates: { canonical: "https://tribultz.com.br" },
  openGraph: {
    title: "Tribultz — Validação CBS/IBS para a Reforma Tributária",
    description:
      "Motor determinístico de conformidade fiscal CBS/IBS. Valide NFe, SPED e catálogo de produtos contra a LC 214 e exporte para o seu ERP.",
    url: "https://tribultz.com.br",
    siteName: "Tribultz",
    locale: "pt_BR",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Tribultz — CBS/IBS | Reforma Tributária LC 214",
    description:
      "Validação determinística de notas fiscais, SPED e catálogo de produtos contra CBS e IBS. Relatório auditável e exportação para ERP.",
  },
};

function Check({ color = "#10B981" }: { color?: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12l4 4L19 6" />
    </svg>
  );
}

function HeroVisual() {
  return (
    <div className="relative px-4 md:px-0">
      <div className="absolute -left-6 -top-4 z-10 hidden items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs font-semibold shadow-lg md:flex">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#E8F0FE] text-[#2956E3]">
          <Check color="#2956E3" />
        </span>
        18 regras validadas
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6" style={{ boxShadow: "0 24px 60px -20px rgba(41,86,227,0.18), 0 4px 12px rgba(36,41,46,0.04)" }}>
        <div className="mb-5 flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">XML · NFe 35250912.345</span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Validado
          </span>
        </div>

        {[
          { label: "CBS", value: "alíquota 8,80%", warn: false },
          { label: "IBS", value: "alíquota 17,70%", warn: false },
          { label: "cClassTrib", value: "0010100", warn: true },
          { label: "CST", value: "000 · Tributação integral", warn: false },
        ].map((row) => (
          <div
            key={row.label}
            className="mb-2 flex items-center justify-between rounded-xl px-4 py-3 text-sm"
            style={{ background: row.warn ? "#FFFBEB" : "#F8FAFC" }}
          >
            <span className="font-semibold text-slate-700">{row.label}</span>
            <span className="font-mono text-slate-600">{row.value}</span>
            <span
              className="rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
              style={row.warn
                ? { background: "#FEF3C7", color: "#B45309" }
                : { background: "#ECFDF5", color: "#047857" }}
            >
              {row.warn ? "CHECK" : "PASS"}
            </span>
          </div>
        ))}

        <div className="mt-4 flex items-center justify-between border-t border-dashed border-slate-200 pt-4 text-sm">
          <span className="text-slate-500">Compliance Score</span>
          <span className="font-mono text-xl font-bold text-emerald-600">94 / 100</span>
        </div>
      </div>

      <div className="absolute -bottom-4 -right-4 z-10 hidden items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs font-semibold shadow-lg md:flex">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg" style={{ background: "#FFFBEB", color: "#B45309" }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 9v4M12 17h.01M10.3 3.86 1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
        </span>
        1 ajuste sugerido
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <>
      <PublicNavbar />

      <main>
        {/* HERO */}
        <section
          className="pb-20 pt-16"
          style={{
            background: `
              radial-gradient(900px 420px at 85% -10%, rgba(41,86,227,0.08), transparent 60%),
              radial-gradient(700px 320px at 0% 40%, rgba(255,214,0,0.08), transparent 60%)
            `,
          }}
        >
          <div className="mx-auto max-w-6xl px-4 md:px-6">
            <div className="grid items-center gap-16 md:grid-cols-2">
              <div>
                <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-[#E8F0FE] py-1.5 pl-1.5 pr-4">
                  <span className="rounded-full bg-[#2956E3] px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-white">
                    LC 214/2025
                  </span>
                  <span className="text-xs font-semibold text-[#2044C7]">Reforma Tributária pronta para 2026</span>
                </div>

                <h1 className="mb-5 text-5xl font-extrabold leading-[1.04] tracking-tight text-[#24292E] md:text-[3.5rem]">
                  IBS e CBS sem erro.<br />
                  Sem multa.{" "}
                  <span className="px-1" style={{ background: "linear-gradient(180deg, transparent 55%, #FFD600 55%)" }}>
                    Sem susto.
                  </span>
                </h1>

                <p className="mb-8 text-lg leading-relaxed text-[#334155]">
                  A Tribultz valida suas notas fiscais no padrão da Reforma Tributária{" "}
                  <strong>antes da emissão</strong>. Compliance automático, sem surpresas.
                </p>

                <div className="flex flex-wrap items-center gap-4">
                  <Link
                    href="/register"
                    className="rounded-lg bg-[#2956E3] px-6 py-3 text-sm font-bold text-white transition-colors hover:bg-[#2044C7]"
                    style={{ boxShadow: "0 8px 24px rgba(41,86,227,0.25)" }}
                  >
                    Criar conta grátis →
                  </Link>
                  <Link href="/diagnostico" className="text-sm font-semibold text-[#2956E3] underline-offset-4 hover:underline">
                    Ver como funciona
                  </Link>
                </div>

                <div className="mt-7 flex flex-wrap gap-5 text-sm text-[#6C757D]">
                  {["Sem cartão de crédito", "5 validações grátis", "Setup em 5 minutos"].map((t) => (
                    <span key={t} className="flex items-center gap-1.5"><Check />{t}</span>
                  ))}
                </div>
              </div>

              <HeroVisual />
            </div>
          </div>
        </section>

        {/* TRUST BAR */}
        <section className="border-y border-slate-200 bg-white py-6">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-10 px-4 md:px-6">
            {[
              { icon: "🛡", label: "Tabela oficial SVRS" },
              { icon: "🔒", label: "LGPD compliant" },
              { icon: "✅", label: "18 regras CBS/IBS LC 214" },
              { icon: "⏱", label: "SLA 99,9% (plano Contador)" },
              { icon: "📄", label: "Auditável (PDF + JSON)" },
            ].map((t) => (
              <span key={t.label} className="flex items-center gap-2 text-sm font-semibold text-[#6C757D]">
                <span>{t.icon}</span>
                {t.label}
              </span>
            ))}
          </div>
        </section>

        {/* HOW IT WORKS */}
        <section className="py-24" id="how">
          <div className="mx-auto max-w-6xl px-4 md:px-6">
            <div className="mb-14 grid gap-10 md:grid-cols-2 md:items-end">
              <div>
                <span className="text-xs font-semibold uppercase tracking-widest text-[#2044C7]">Como funciona</span>
                <h2 className="mt-3 text-4xl font-extrabold leading-tight tracking-tight text-[#24292E]">
                  Três passos da integração à emissão segura
                </h2>
              </div>
              <p className="text-base leading-relaxed text-[#334155]">
                Seu ERP envia o XML, nosso motor valida contra as 18 regras da LC 214, você emite com a evidência auditável.
              </p>
            </div>

            <div className="grid gap-5 md:grid-cols-3">
              {[
                { n: "1", title: "Conecte seu sistema", body: "Integre via API REST ou envie diretamente o arquivo SPED/XML. Sem mudanças no seu ERP." },
                { n: "2", title: "Valide automaticamente", body: "O motor CBS/IBS analisa cada nota em segundos: alíquotas, cClassTrib, CST e bases de cálculo." },
                { n: "3", title: "Emita com segurança", body: "Relatório auditável com base legal por finding. Zero surpresas na fiscalização." },
              ].map((step) => (
                <div key={step.n} className="rounded-2xl border border-slate-200 bg-white p-8">
                  <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-xl bg-[#2956E3] font-mono text-base font-bold text-white">
                    {step.n}
                  </div>
                  <h3 className="mb-3 text-xl font-bold">{step.title}</h3>
                  <p className="text-sm leading-relaxed text-[#334155]">{step.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* FEATURES */}
        <section className="py-24" style={{ background: "#F8FAFC" }}>
          <div className="mx-auto max-w-6xl px-4 md:px-6">
            <div className="mb-14 grid gap-10 md:grid-cols-2 md:items-end">
              <div>
                <span className="text-xs font-semibold uppercase tracking-widest text-[#2044C7]">Produtos</span>
                <h2 className="mt-3 text-4xl font-extrabold leading-tight tracking-tight text-[#24292E]">
                  Toda a Reforma Tributária em uma plataforma
                </h2>
              </div>
              <p className="text-base leading-relaxed text-[#334155]">
                Três frentes complementares: validação de catálogo, classificação tributária e governança contínua.
              </p>
            </div>

            <div className="grid gap-5 md:grid-cols-3">
              {[
                {
                  badge: "SPED FISCAL",
                  preview: [
                    { l: "EFD-ICMS/IPI · 12.430 itens", r: "✓", ok: true },
                    { l: "Catálogo CBS/IBS", r: "100%", ok: true },
                    { l: "CSV pronto p/ ERP", r: "↓", ok: false },
                  ],
                  title: "SPED Fiscal",
                  body: "Envie o EFD-ICMS/IPI e valide todo o catálogo de produtos contra as regras CBS/IBS. CSV pronto para o ERP.",
                  meta: "EFD-ICMS/IPI · cBenef · cClassTrib",
                },
                {
                  badge: "cClassTrib · LC 214",
                  preview: [
                    { l: "0010100 · Padrão", r: "8,80%", ok: true },
                    { l: "0020010 · Reduzido 60%", r: "3,52%", ok: true },
                    { l: "0030005 · Cesta básica", r: "0%", ok: true },
                  ],
                  title: "cClassTrib LC 214",
                  body: "Valide a nova classificação tributária da Reforma. Alíquotas CBS/IBS sincronizadas com a tabela oficial SVRS.",
                  meta: "Sincronização semanal · 1.247 códigos",
                },
                {
                  badge: "COMPLIANCE SCORE",
                  preview: [
                    { l: "Outubro 2025", r: "94/100", ok: true },
                    { l: "Setembro 2025", r: "91/100", ok: false },
                    { l: "Tendência", r: "↑ +3 pts", ok: true },
                  ],
                  title: "Compliance Score",
                  body: "Acompanhe o índice mensal de conformidade da sua empresa e atue antes da fiscalização.",
                  meta: "Alertas · tendência · benchmark setor",
                },
              ].map((f) => (
                <div key={f.badge} className="flex flex-col rounded-2xl border border-slate-200 bg-white p-8 transition-all hover:-translate-y-0.5 hover:border-[#8db1f8]">
                  <span className="mb-5 self-start rounded-full bg-[#E8F0FE] px-3 py-1 font-mono text-[11px] font-bold uppercase tracking-wider text-[#2044C7]">
                    {f.badge}
                  </span>
                  <div className="mb-5 rounded-xl bg-[#F8FAFC] p-4 font-mono text-xs space-y-2">
                    {f.preview.map((p) => (
                      <div key={p.l} className="flex justify-between">
                        <span className="text-slate-500">{p.l}</span>
                        <span className={p.ok ? "font-bold text-emerald-600" : "text-[#2956E3]"}>{p.r}</span>
                      </div>
                    ))}
                  </div>
                  <h3 className="mb-3 text-xl font-bold">{f.title}</h3>
                  <p className="mb-6 flex-1 text-sm leading-relaxed text-[#334155]">{f.body}</p>
                  <div className="flex items-center justify-between border-t border-dashed border-slate-200 pt-5 text-xs font-semibold text-[#6C757D]">
                    <span>{f.meta}</span>
                    <span className="text-[#2956E3]">→</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* NEWS */}
        <section className="py-16">
          <div className="mx-auto max-w-6xl px-4 md:px-6">
            <h2 className="mb-8 text-2xl font-bold text-[#24292E]">Últimas novidades</h2>
            <NewsFeed />
          </div>
        </section>

        {/* FINAL CTA */}
        <section
          className="relative overflow-hidden py-24"
          style={{ background: "linear-gradient(135deg, #2956E3 0%, #1a328b 100%)" }}
        >
          <div
            className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full"
            style={{ background: "radial-gradient(circle, rgba(255,214,0,0.15), transparent 70%)" }}
          />
          <div className="relative mx-auto max-w-6xl px-4 md:px-6">
            <div className="grid items-center gap-12 md:grid-cols-[1.3fr_1fr]">
              <div>
                <h2 className="mb-4 text-4xl font-extrabold leading-tight tracking-tight text-white md:text-5xl">
                  Comece <span style={{ color: "#FFD600" }}>grátis</span> hoje.<br />
                  Reforma chega em 2026.
                </h2>
                <p className="mb-8 text-lg leading-relaxed" style={{ color: "rgba(255,255,255,0.8)" }}>
                  5 validações de cortesia, 18 regras CBS/IBS, diagnóstico imediato. Sem cartão de crédito.
                </p>
                <div className="flex flex-wrap items-center gap-4">
                  <Link
                    href="/register"
                    className="rounded-lg px-6 py-3 text-sm font-bold text-[#24292E] transition-colors hover:brightness-95"
                    style={{ background: "#FFD600" }}
                  >
                    Criar conta grátis
                  </Link>
                  <Link href="/pricing" className="text-sm font-semibold text-white underline underline-offset-4 opacity-80 hover:opacity-100">
                    Ver todos os planos
                  </Link>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {[
                  { n: "2.847", l: "Empresas usando hoje" },
                  { n: "1.2M", l: "XMLs validados" },
                  { n: "18", l: "Regras CBS/IBS" },
                  { n: "99,9%", l: "SLA disponível" },
                ].map((s) => (
                  <div
                    key={s.l}
                    className="rounded-xl p-5"
                    style={{ background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)" }}
                  >
                    <div className="font-mono text-3xl font-bold" style={{ color: "#FFD600" }}>{s.n}</div>
                    <div className="mt-1 text-xs font-medium" style={{ color: "rgba(255,255,255,0.65)" }}>{s.l}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      </main>

      <PublicFooter />
    </>
  );
}
