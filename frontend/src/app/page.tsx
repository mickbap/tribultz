import type { Metadata } from "next";
import Link from "next/link";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { WhatsAppLink } from "@/components/public/WhatsAppLink";
import { PublicFooter } from "@/components/public/PublicFooter";
import { NewsFeed } from "@/components/public/NewsFeed";
import { RULES_COUNT, CLASSTRIB_COUNT } from "@/lib/validation/rulesMeta";

export const metadata: Metadata = {
  title: "IBS e CBS sem Rejeição de NF-e — Compliance LC 214",
  description: `Rejeição 1024 por cClassTrib errado? Penalidades CBS/IBS a partir de agosto/2026. Valide CST × cClassTrib e ${RULES_COUNT} regras da Reforma, calcule CBS/IBS e exporte para TOTVS/SAP/Omie/Linx. 100 créditos API grátis.`,
  keywords: [
    "Rejeição 1024 NF-e", "cClassTrib CBS IBS", "NCM cClassTrib LC 214",
    "penalidades CBS IBS 2026", "validação NF-e reform tributária",
    "compliance CBS IBS", "API NCM classificação", "TOTVS SAP Omie Linx CBS IBS",
  ],
  openGraph: {
    title: "IBS e CBS sem Rejeição de NF-e | Tribultz",
    description: "Evite a Rejeição 1024. Valide CST × cClassTrib e calcule CBS/IBS antes das penalidades de agosto/2026.",
  },
};

const WA_NUMBER = "5551991881026";
const WA_MSG = encodeURIComponent("Olá! Vim pelo site da Tribultz e quero saber mais sobre validação CBS/IBS.");
const WA_URL = `https://wa.me/${WA_NUMBER}?text=${WA_MSG}`;
const WA_REJEICAO = `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent("Olá! Estou com Rejeição 1024 na NF-e (cClassTrib incorreto) e preciso de ajuda urgente.")}`;
const WA_ERP = `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent("Olá! Preciso integrar CBS/IBS ao meu ERP (TOTVS/SAP/Omie/Linx) e quero entender como a Tribultz pode ajudar.")}`;

const JSON_LD = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://tribultz.com.br/#org",
      "name": "Tribultz",
      "url": "https://tribultz.com.br",
      "logo": "https://tribultz.com.br/logo.png",
      "contactPoint": { "@type": "ContactPoint", "contactType": "customer support", "availableLanguage": "Portuguese" },
    },
    {
      "@type": "SoftwareApplication",
      "name": "Tribultz",
      "applicationCategory": "BusinessApplication",
      "operatingSystem": "Web",
      "offers": { "@type": "Offer", "price": "0", "priceCurrency": "BRL", "description": "100 créditos API grátis" },
      "description": "Plataforma de validação CBS/IBS e compliance para a Reforma Tributária brasileira (LC 214): cálculo CBS/IBS e validação de CST × cClassTrib.",
    },
    {
      "@type": "FAQPage",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "O que é a Rejeição 1024 na NF-e com CBS/IBS?",
          "acceptedAnswer": { "@type": "Answer", "text": "A Rejeição 1024 ocorre quando o cClassTrib informado na NF-e é incompatível com o CST do produto, tornando-se o erro mais comum desde janeiro/2026. A Tribultz valida essa compatibilidade automaticamente antes da emissão e indica a correção necessária." },
        },
        {
          "@type": "Question",
          "name": "Quando começam as penalidades por erro em CBS/IBS?",
          "acceptedAnswer": { "@type": "Answer", "text": "As penalidades efetivas por erros de CBS/IBS em NF-e começam em agosto/2026, encerrando o período educacional da Receita Federal. Empresas com cClassTrib incorreto ficarão sujeitas a autuações e multas." },
        },
        {
          "@type": "Question",
          "name": "Como classificar o NCM correto para o cClassTrib na Reforma Tributária?",
          "acceptedAnswer": { "@type": "Answer", "text": "O cClassTrib é determinado pelo capítulo NCM e pelo regime tributário aplicável (padrão, reduzido, cesta básica, imune, etc). A Tribultz valida a compatibilidade CST × cClassTrib (a fonte da Rejeição 1024) e calcula CBS/IBS com evidência auditável da base legal; a sugestão automática de cClassTrib a partir do NCM está em ativação e deve ser validada." },
        },
        {
          "@type": "Question",
          "name": "Como integrar CBS/IBS no TOTVS, SAP, Omie ou Linx?",
          "acceptedAnswer": { "@type": "Answer", "text": "A Tribultz exporta o catálogo de produtos validado nos formatos TOTVS Protheus, SAP Business One, Omie, Linx e CSV genérico, prontos para importação direta no ERP sem alterações manuais." },
        },
        {
          "@type": "Question",
          "name": "O que é o split payment e quando entra em vigor?",
          "acceptedAnswer": { "@type": "Answer", "text": "O split payment é o mecanismo de retenção automática de IBS/CBS no momento do pagamento (Pix, boleto, transferência bancária), previsto para entrar em vigor em 2027. Impacta diretamente o capital de giro — empresas devem modelar o impacto antes do prazo." },
        },
      ],
    },
  ],
};

function WhatsAppIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
    </svg>
  );
}

function WhatsAppButton({ label = "Falar pelo WhatsApp", variant = "green", source = "cta" }: { label?: string; variant?: "green" | "outline-white" | "outline-dark"; source?: string }) {
  const styles: Record<string, React.CSSProperties> = {
    green: { background: "#25D366", color: "#fff", boxShadow: "0 8px 24px rgba(37,211,102,0.30)" },
    "outline-white": { background: "transparent", color: "#fff", border: "1.5px solid rgba(255,255,255,0.55)" },
    "outline-dark": { background: "transparent", color: "#25D366", border: "1.5px solid #25D366" },
  };
  return (
    <WhatsAppLink
      href={WA_URL}
      source={source}
      className="inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-bold transition-all hover:brightness-95 hover:scale-[1.02]"
      style={styles[variant]}
    >
      <WhatsAppIcon />
      {label}
    </WhatsAppLink>
  );
}

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
        {RULES_COUNT} regras validadas
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
                <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-[#FEF2F2] py-1.5 pl-1.5 pr-4">
                  <span className="rounded-full bg-[#DC2626] px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-white">
                    ATIVO
                  </span>
                  <span className="text-xs font-semibold text-[#991B1B]">Penalidades CBS/IBS a partir de agosto/2026</span>
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
                  <WhatsAppButton label="Falar com a gente" variant="outline-dark" source="hero" />
                  <Link href="/diagnostico" className="text-sm font-semibold text-[#2956E3] underline-offset-4 hover:underline">
                    Ver como funciona
                  </Link>
                </div>

                <div className="mt-7 flex flex-wrap gap-5 text-sm text-[#6C757D]">
                  {["Sem cartão de crédito", "5 validações grátis", "100 créditos API grátis"].map((t) => (
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
              { icon: "🔌", label: "API de cálculo CBS/IBS" },
              { icon: "✅", label: `${RULES_COUNT} regras CBS/IBS LC 214` },
              { icon: "🔗", label: "TOTVS · SAP · Omie · Linx" },
              { icon: "📄", label: "Auditável (PDF + JSON)" },
              { icon: "🔔", label: "Trial gerenciado · avisos D-3 e D-1" },
              { icon: "📡", label: "Monitoramento 24/7" },
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
                Seu ERP envia o XML, nosso motor valida contra as {RULES_COUNT} regras da LC 214, você emite com a evidência auditável.
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

        {/* WHATSAPP STRIP — entre "Como Funciona" e "Produtos" */}
        <section className="border-y border-slate-200 bg-white py-10">
          <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-4 md:flex-row md:px-6">
            <div>
              <p className="text-base font-bold text-[#24292E]">NF-e rejeitada? Penalidades CBS/IBS chegam em agosto/2026.</p>
              <p className="mt-1 text-sm text-[#334155]">Nosso time fiscal responde em minutos — sem enrolação. <span className="font-semibold">(51) 99188-1026</span>.</p>
            </div>
            <WhatsAppButton label="Chamar agora" variant="green" source="cta_meio" />
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

            <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
              {[
                {
                  badge: "SPED FISCAL",
                  preview: [
                    { l: "EFD-ICMS/IPI · validação CBS/IBS", r: "✓", ok: true },
                    { l: "Catálogo CBS/IBS", r: "100%", ok: true },
                    { l: "Export TOTVS / SAP / Omie", r: "↓", ok: false },
                  ],
                  title: "SPED Fiscal",
                  body: "Envie o EFD-ICMS/IPI e valide todo o catálogo de produtos contra as regras CBS/IBS. Export pronto para TOTVS, SAP, Omie, Linx ou CSV genérico.",
                  meta: "EFD-ICMS/IPI · TOTVS · SAP · Omie · Linx",
                },
                {
                  badge: "cClassTrib · LC 214",
                  preview: [
                    { l: "0010100 · Padrão", r: "8,80%", ok: true },
                    { l: "0020010 · Reduzido 60%", r: "3,52%", ok: true },
                    { l: "0030005 · Cesta básica", r: "0%", ok: true },
                  ],
                  title: "cClassTrib LC 214",
                  body: "Valide a nova classificação tributária da Reforma. Alíquotas CBS/IBS conforme a tabela oficial SVRS.",
                  meta: "Tabela oficial SVRS · NT 2025.002-RTC v1.40",
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
                {
                  badge: "API · PAY-PER-CALL",
                  preview: [
                    { l: "POST /classify", r: "CBS/IBS calculado", ok: true },
                    { l: "CBS 8,80% + IBS 17,70% (ref. plena)", r: "26,50%", ok: true },
                    { l: "1 crédito / chamada", r: "100 grátis", ok: false },
                  ],
                  title: "API Classify",
                  body: "Calcule CBS/IBS direto no seu ERP via API. Classificação NCM→cClassTrib em ativação (sugestão a validar). 100 créditos grátis. Sem contrato — pague só o que usar.",
                  meta: "X-API-Key · REST · JSON",
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

        {/* REJEIÇÃO 1024 — CTA após produtos, alta urgência */}
        <section className="border-y border-red-200 bg-red-50 py-10">
          <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 md:flex-row md:items-center md:justify-between md:px-6">
            <div>
              <p className="text-base font-bold text-red-800">NF sendo rejeitada por cClassTrib incorreto?</p>
              <p className="mt-1 text-sm text-red-700">
                A <strong>Rejeição 1024</strong> é o erro mais comum desde jan/2026 — incompatibilidade entre CST e cClassTrib.
                Nosso time resolve ao vivo no WhatsApp.
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-3">
              <WhatsAppLink
                href={WA_REJEICAO}
                source="rejeicao_1024"
                className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-red-700"
              >
                <WhatsAppIcon size={16} />
                Resolver a Rejeição 1024
              </WhatsAppLink>
              <WhatsAppLink
                href={WA_ERP}
                source="integrar_erp"
                className="inline-flex items-center gap-2 rounded-lg border border-red-300 bg-white px-5 py-2.5 text-sm font-semibold text-red-700 hover:bg-red-50"
              >
                Integrar ao ERP →
              </WhatsAppLink>
            </div>
          </div>
        </section>

        {/* FOUNDING PARTNERS — teaser institucional */}
        <section className="border-y border-slate-200 bg-[#F4F7FF] py-16">
          <div className="mx-auto flex max-w-6xl flex-col items-start gap-6 px-4 md:flex-row md:items-center md:justify-between md:px-6">
            <div className="max-w-2xl">
              <span className="text-xs font-semibold uppercase tracking-wide text-[#2956E3]">Programa Founding Partners</span>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-[#24292E]">Construa a Tribultz conosco</h2>
              <p className="mt-3 text-slate-600">
                Estamos formando um grupo seleto de empresas para construir a plataforma durante a
                Reforma Tributária. Não é um teste de software — é construção conjunta com quem vive
                a operação fiscal todos os dias.
              </p>
            </div>
            <Link
              href="/founding-partners"
              className="flex-none rounded-lg bg-[#2956E3] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#2044C7]"
              style={{ boxShadow: "0 8px 24px rgba(41,86,227,0.20)" }}
            >
              Conhecer o Programa
            </Link>
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
                  5 validações de cortesia, {RULES_COUNT} regras CBS/IBS, diagnóstico imediato. Sem cartão de crédito.
                </p>
                <div className="flex flex-wrap items-center gap-4">
                  <Link
                    href="/register"
                    className="rounded-lg px-6 py-3 text-sm font-bold text-[#24292E] transition-colors hover:brightness-95"
                    style={{ background: "#FFD600" }}
                  >
                    Criar conta grátis
                  </Link>
                  <WhatsAppButton label="Falar com um especialista" variant="outline-white" source="cta_final" />
                  <Link href="/pricing" className="text-sm font-semibold text-white underline underline-offset-4 opacity-80 hover:opacity-100">
                    Ver todos os planos
                  </Link>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {[
                  { n: String(RULES_COUNT), l: "Regras CBS/IBS validadas" },
                  { n: String(CLASSTRIB_COUNT), l: "Classificações cClassTrib mapeadas (SVRS)" },
                  { n: "100", l: "Créditos API grátis" },
                  { n: "5 min", l: "Monitoramento contínuo" },
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

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
      />
    </>
  );
}
