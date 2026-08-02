/**
 * /calculadora — server-rendered (#296).
 *
 * Antes: page client-side com 61 palavras servidas ao Googlebot.
 * Agora: copy explanatório SSR + widget Calculator interativo isolado.
 */

import { Calculator } from "./Calculator";
import { FundamentacaoLegal } from "@/components/seo/FundamentacaoLegal";

const FAQ = [
  {
    q: "As alíquotas da calculadora estão atualizadas com a NT 2025.002 e LC 227?",
    a: "Sim. A base de alíquotas é sincronizada com o Convênio ICMS 142/2018, a tabela cClassTrib SVRS (atualização de 15/abr/2026) e os regulamentos IBS/CBS publicados pela Receita Federal e Comitê Gestor em 30/abr/2026.",
  },
  {
    q: "A calculadora considera regimes especiais e cesta básica?",
    a: "Sim. O cClassTrib informado resolve o regime aplicável (padrão, reduzido, cesta básica nacional, monofásico, imune, ZFM) e a calculadora aplica o modificador de alíquota correspondente conforme os Anexos da LC 214.",
  },
  {
    q: "Como a base de cálculo é determinada?",
    a: "A base de cálculo é o valor da operação, líquido de descontos e abatimentos. Para 2026 (período de teste com alíquotas reduzidas de 0,9% CBS e 0,1% IBS), o ICMS destacado integra a base — situação que se inverte progressivamente até 2033 conforme o cronograma da LC 214.",
  },
  {
    q: "Posso usar a calculadora sem login?",
    a: "Sim. A versão web é 100% gratuita, sem cadastro, com limite de 100 cálculos por dia por IP. Para volume maior, integre via API com o plano Starter (X-API-Key) ou Profissional (sem limite).",
  },
  {
    q: "A calculadora gera o XML para o ERP?",
    a: "Sim. Após o cálculo, exibimos o snippet XML pronto para o grupo gIBSCBS da NF-e, com todos os atributos calculados (vBC, pCBS, vCBS, pIBSUF, vIBSUF, pIBSMun, vIBSMun, vIBS). Suficiente para colar no template do seu emissor.",
  },
  {
    q: "Como diferenciar o IBS estadual do municipal?",
    a: "O IBS é uno mas internamente repartido entre UF e Município conforme o destino da operação. A calculadora retorna pIBSUF e pIBSMun separadamente. Em operações interestaduais, o valor é integralmente devido ao destino conforme regra da LC 214 art. 156-A.",
  },
];

const LEGAL_REFS = [
  {
    instrumento: "LC 214/2025",
    artigo: "arts. 8º a 22, 156-A",
    descricao: "Base legal da CBS e IBS e definição de base de cálculo. Alíquotas de referência do regime cheio: CBS ~8,8% / IBS ~17,7%; fase de teste de 2026: CBS 0,9% / IBS 0,1%.",
    link: "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp214.htm",
  },
  {
    instrumento: "LC 214/2025",
    artigo: "art. 348, §§ 3º e 4º (incluídos pela LC 227/2026)",
    descricao: "Período Pedagógico — autuado exclusivamente por obrigação acessória de IBS/CBS tem 60 dias contados da notificação para regularizar, extinguindo a penalidade.",
  },
  {
    instrumento: "Regulamento IBS",
    artigo: "publicação 30/abr/2026",
    descricao: "Detalha operacionalização do IBS pelo Comitê Gestor (Estados + Municípios).",
  },
  {
    instrumento: "Regulamento CBS",
    artigo: "publicação 30/abr/2026",
    descricao: "Detalha operacionalização da CBS pela Receita Federal (esfera federal).",
  },
  {
    instrumento: "NT 2025.002-RTC v1.36",
    artigo: "grupos gIBSCBS, gIBSCBSMono",
    descricao: "Layout XML NF-e com campos vBC, pCBS, vCBS, pIBSUF, vIBSUF, pIBSMun, vIBSMun, vIBS.",
  },
  {
    instrumento: "Tabela cClassTrib SVRS",
    artigo: "publicação 15/abr/2026",
    descricao: "Lista oficial de cClassTrib com p_CBS, p_IBS e regime especial por código.",
    link: "https://dfe-portal.svrs.rs.gov.br/Cff/ClassificacaoTributaria",
  },
];

export default function CalculadoraPage() {
  return (
    <>
      {/* Hero SSR */}
      <section className="bg-gradient-to-br from-emerald-50 to-white px-4 py-16 text-center md:py-20">
        <div className="mx-auto max-w-3xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-emerald-100 px-4 py-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-xs font-semibold text-emerald-700">Alíquota de referência (regime cheio · LC 214)</span>
          </div>
          <h1 className="text-3xl font-extrabold leading-tight text-slate-900 md:text-4xl">
            Calculadora CBS/IBS<br />
            <span className="text-emerald-600">por NCM, UF e CST</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-600">
            Calcule CBS e IBS para cada item da sua NF-e com alíquotas oficiais.
            Retorna o XML pronto para o grupo gIBSCBS e a base legal.
          </p>
          <div className="mx-auto mt-2 flex flex-wrap items-center justify-center gap-4 text-sm text-slate-400">
            <span>100 cálculos gratuitos/dia</span>
            <span>·</span>
            <span>Sem login</span>
            <span>·</span>
            <span>LC 214 · Regulamento IBS/CBS 30/abr/2026</span>
          </div>
        </div>
      </section>

      {/* Calculadora interativa */}
      <Calculator />

      {/* SSR explanatory content */}
      <section className="border-t border-slate-200 bg-white py-12">
        <div className="mx-auto max-w-3xl px-4 space-y-10">
          <div>
            <h2 className="mb-3 text-2xl font-bold text-slate-900">Como a calculadora funciona</h2>
            <p className="text-slate-700">
              Você informa quatro parâmetros: <strong>UF de destino</strong>, <strong>NCM</strong> (opcional),
              <strong> CST</strong> do IBS/CBS e <strong>valor da base de cálculo</strong>. A partir desses
              dados, a calculadora resolve o cClassTrib aplicável na tabela SVRS, identifica a alíquota
              de CBS e IBS conforme a LC 214 e os Anexos, e calcula os valores em centavos com
              arredondamento conforme a regra da NT 2025.002-RTC.
            </p>
            <p className="mt-3 text-slate-700">
              O resultado inclui o snippet XML pronto para colar no emissor da NF-e, dentro do grupo
              <code className="rounded bg-slate-100 px-1 font-mono text-sm"> gIBSCBS</code>. Para operações
              interestaduais, o IBS é repartido em UF e Município conforme o destino — campos
              <code className="rounded bg-slate-100 px-1 font-mono text-sm"> pIBSUF</code> e
              <code className="rounded bg-slate-100 px-1 font-mono text-sm"> pIBSMun</code> são retornados separados.
            </p>
          </div>

          <div>
            <h2 className="mb-3 text-2xl font-bold text-slate-900">Alíquotas vigentes em 2026</h2>
            <p className="text-slate-700">
              2026 é o <strong>ano-teste</strong> da Reforma Tributária. As alíquotas de referência são
              significativamente reduzidas em relação às projetadas para o regime cheio (2033+),
              servindo de calibração para os sistemas:
            </p>
            <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">Tributo</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">Alíquota 2026</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">Alíquota referência (regime cheio)</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">Base legal</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-slate-100">
                    <td className="px-4 py-2 font-mono">CBS</td>
                    <td className="px-4 py-2 font-mono">0,9%</td>
                    <td className="px-4 py-2 font-mono">~8,8%</td>
                    <td className="px-4 py-2">LC 214 art. 18</td>
                  </tr>
                  <tr className="border-t border-slate-100">
                    <td className="px-4 py-2 font-mono">IBS</td>
                    <td className="px-4 py-2 font-mono">0,1%</td>
                    <td className="px-4 py-2 font-mono">~17,7%</td>
                    <td className="px-4 py-2">LC 214 art. 156-A</td>
                  </tr>
                  <tr className="border-t border-slate-100">
                    <td className="px-4 py-2 font-mono">Total IVA dual</td>
                    <td className="px-4 py-2 font-mono">1,0%</td>
                    <td className="px-4 py-2 font-mono">~26,5%</td>
                    <td className="px-4 py-2">—</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-sm text-slate-600">
              Em 2026 não há recolhimento efetivo do CBS/IBS (LC 214 art. 348 — período de aprendizado).
              Desde 01/08/2026 a multa por obrigação acessória de IBS/CBS é aplicável (Ato Conjunto
              RFB/CGIBS nº 1/2025, art. 3º); se autuado exclusivamente por essa obrigação, o contribuinte
              tem 60 dias contados da notificação para regularizar, extinguindo a penalidade (art. 348,
              §§ 3º e 4º, da LC 214/2025, incluídos pela LC 227/2026). A partir de 2027 o CBS começa a
              ser cobrado efetivamente.
            </p>
          </div>

          <div>
            <h2 className="mb-3 text-2xl font-bold text-slate-900">Regimes especiais cobertos</h2>
            <p className="text-slate-700">
              A calculadora aplica modificadores de alíquota para os regimes especiais previstos
              nos Anexos da LC 214:
            </p>
            <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">CST</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">Regime</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">Modificador</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">Aplicação típica</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-slate-100"><td className="px-4 py-2 font-mono">000</td><td className="px-4 py-2">Tributação normal</td><td className="px-4 py-2 font-mono">100%</td><td className="px-4 py-2">Bens e serviços padrão</td></tr>
                  <tr className="border-t border-slate-100"><td className="px-4 py-2 font-mono">001</td><td className="px-4 py-2">Redução</td><td className="px-4 py-2 font-mono">60%</td><td className="px-4 py-2">Anexo III (saúde, educação)</td></tr>
                  <tr className="border-t border-slate-100"><td className="px-4 py-2 font-mono">002</td><td className="px-4 py-2">Ad rem (monofásico)</td><td className="px-4 py-2 font-mono">100%</td><td className="px-4 py-2">Combustíveis, bebidas alcoólicas</td></tr>
                  <tr className="border-t border-slate-100"><td className="px-4 py-2 font-mono">070</td><td className="px-4 py-2">Imunidade/Isenção</td><td className="px-4 py-2 font-mono">0%</td><td className="px-4 py-2">Cesta básica nacional, exportação</td></tr>
                  <tr className="border-t border-slate-100"><td className="px-4 py-2 font-mono">200</td><td className="px-4 py-2">Diferimento</td><td className="px-4 py-2 font-mono">100% (postergado)</td><td className="px-4 py-2">B2B com crédito presumido</td></tr>
                  <tr className="border-t border-slate-100"><td className="px-4 py-2 font-mono">410</td><td className="px-4 py-2">Suspensão</td><td className="px-4 py-2 font-mono">0%</td><td className="px-4 py-2">Drawback, ZFM</td></tr>
                  <tr className="border-t border-slate-100"><td className="px-4 py-2 font-mono">620</td><td className="px-4 py-2">Monofásico downstream</td><td className="px-4 py-2 font-mono">0% para distribuidores</td><td className="px-4 py-2">Combustíveis (downstream)</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h2 className="mb-3 text-2xl font-bold text-slate-900">Quando o cálculo manual falha</h2>
            <p className="text-slate-700">
              Os erros mais comuns vistos em produção desde janeiro/2026:
            </p>
            <ul className="mt-3 list-disc space-y-2 pl-6 text-slate-700">
              <li><strong>Confundir alíquota nominal com efetiva.</strong> Operações com redução (CST 001) calculam sobre alíquota cheia × modificador 60%. Erro comum: aplicar 0,054% direto sem registrar como redução.</li>
              <li><strong>Aplicar IBS único sem repartir UF/Município.</strong> O XML exige <code className="font-mono">pIBSUF + pIBSMun</code> separados — somar e informar tudo em pIBSUF gera Rejeição 1024 cruzada.</li>
              <li><strong>Esquecer arredondamento por item.</strong> A NT 2025.002 exige arredondamento HALF_UP em duas casas por item, depois soma do total. Calcular sobre o total agregado gera divergência de centavos no IBSCBSTot.</li>
              <li><strong>Não considerar o destino interestadual.</strong> Em operações interestaduais, a UF de destino é a referência — não a do emitente.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* FAQ SSR */}
      <section className="border-t border-slate-200 bg-white py-12">
        <div className="mx-auto max-w-3xl px-4">
          <h2 className="mb-8 text-2xl font-bold text-slate-900">Perguntas frequentes</h2>
          <div className="space-y-6">
            {FAQ.map((item) => (
              <div key={item.q} className="border-b border-slate-100 pb-6 last:border-0">
                <h3 className="font-semibold text-slate-800">{item.q}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <FundamentacaoLegal items={LEGAL_REFS} />
    </>
  );
}
