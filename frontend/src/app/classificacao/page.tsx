/**
 * /classificacao — server-rendered (#296).
 *
 * Antes: page client-side com 0 palavras servidas ao Googlebot.
 * Agora: copy explanatório SSR + widget interativo isolado em <Classifier />.
 *
 * Não usar "use client" aqui — esta página é server component.
 */

import { Classifier } from "./Classifier";
import { CLASSTRIB_CESTA_BASICA } from "@/lib/validation/classtribExamples";
import { CONFIANCA_ALTA_PCT, CONFIANCA_MINIMA_PCT, REGUA_CONFIANCA } from "@/lib/validation/confianca";
import { FundamentacaoLegal } from "@/components/seo/FundamentacaoLegal";
import { RULES_COUNT } from "@/lib/validation/rulesMeta";

const FAQ = [
  {
    q: "O que é cClassTrib e por que ele causa rejeições de NF-e?",
    a: "O cClassTrib é um código de 6 dígitos da LC 214/2025 que define o regime tributário de CBS e IBS de cada produto. Quando ele é incompatível com o CST informado no XML, a SEFAZ rejeita a nota com o código 1024. A classificação correta exige mapear o NCM do produto para o regime aplicável (padrão, reduzido, cesta básica, monofásico, imune, etc).",
  },
  {
    q: "Quando começam as penalidades por cClassTrib incorreto?",
    a: "Desde 01/08/2026 a multa por obrigação acessória de IBS/CBS é aplicável (Ato Conjunto RFB/CGIBS nº 1/2025, art. 3º). Se autuado exclusivamente por essa obrigação, o contribuinte é notificado e tem 60 dias contados da notificação para regularizar, extinguindo a penalidade (art. 348, §§ 3º e 4º, da LC 214/2025, incluídos pela LC 227/2026).",
  },
  {
    q: "Como funciona a classificação automática NCM → cClassTrib?",
    a: `Nossa IA analisa a descrição do produto e sugere o NCM mais adequado conforme a TIPI (Decreto 11.158/2022). A partir do capítulo NCM, mapeamos o cClassTrib conforme a tabela oficial da SVRS (NT 2025.002-RTC v1.40). O resultado inclui um indicador de confiança — valores abaixo de ${CONFIANCA_MINIMA_PCT}% devem ser confirmados com o contador.`,
  },
  {
    q: "Posso usar o NCM sugerido diretamente na NF-e?",
    a: `O NCM sugerido é referência baseada em IA para agilizar a classificação. Confiança acima de ${CONFIANCA_ALTA_PCT}% indica alta probabilidade de acerto, mas recomendamos sempre validar com o contador responsável pelo SPED antes de usar em produção. A Tribultz oferece validação completa das ${RULES_COUNT} regras CBS/IBS para confirmação.`,
  },
  {
    q: "Qual a diferença entre NCM e cClassTrib?",
    a: "NCM é o código de 8 dígitos que identifica o produto na Nomenclatura Comum do Mercosul (tabela TIPI). cClassTrib é o código de 6 dígitos da LC 214 que define como esse produto é tributado pelo IBS e CBS na Reforma Tributária. Um mesmo NCM pode ter diferentes cClassTrib dependendo do regime fiscal aplicável (padrão, reduzido, cesta básica, monofásico, imune).",
  },
  {
    q: "O cClassTrib muda com base no destinatário ou na operação?",
    a: "Sim. Algumas operações específicas (cashback para pessoa física, exportação, regimes diferenciados como Zona Franca de Manaus) podem alterar o cClassTrib aplicável. Por isso a Tribultz combina NCM + regime de operação + destinatário antes de sugerir o código final.",
  },
];

const LEGAL_REFS = [
  {
    instrumento: "LC 214/2025",
    artigo: "arts. 8º a 22, 156-A, 195",
    descricao: "Institui IBS e CBS, base de cálculo, regimes específicos, não-cumulatividade plena.",
    link: "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp214.htm",
  },
  {
    instrumento: "LC 214/2025",
    artigo: "art. 348, §§ 3º e 4º (incluídos pela LC 227/2026)",
    descricao: "Período Pedagógico — autuado exclusivamente por obrigação acessória de IBS/CBS tem 60 dias contados da notificação para regularizar, extinguindo a penalidade.",
  },
  {
    instrumento: "NT 2025.002-RTC v1.36",
    artigo: "campos cClassTrib, gIBSCBS, gIBSCBSMono",
    descricao: "Especificação técnica do layout NF-e para CBS/IBS, validação cruzada CST × cClassTrib (origem da Rejeição 1024).",
  },
  {
    instrumento: "Tabela cClassTrib SVRS",
    artigo: "publicação 15/abr/2026",
    descricao: "Lista oficial de códigos cClassTrib com p_CBS, p_IBS, regime especial e vigência por código.",
    link: "https://dfe-portal.svrs.rs.gov.br/Cff/ClassificacaoTributaria",
  },
  {
    instrumento: "Convênio ICMS 142/2018",
    artigo: "Anexos II-XXVI",
    descricao: "Convenio CONFAZ que lista os NCMs sujeitos a Substituição Tributária e respectivos CEST.",
  },
  {
    instrumento: "Decreto 11.158/2022",
    artigo: "TIPI",
    descricao: "Tabela vigente do IPI e NCM. Base oficial para validação do código NCM.",
  },
];

export default function ClassificacaoPage() {
  return (
    <>
      {/* Hero SSR */}
      <section className="bg-gradient-to-br from-blue-50 to-white px-4 py-16 text-center md:py-20">
        <div className="mx-auto max-w-3xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-red-100 px-4 py-1.5">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            <span className="text-xs font-semibold text-red-700">Penalidades CBS/IBS a partir de agosto/2026</span>
          </div>
          <h1 className="text-3xl font-extrabold leading-tight text-slate-900 md:text-4xl">
            Classifique NCM → cClassTrib<br />
            <span className="text-blue-600">e evite a Rejeição 1024</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-600">
            Descreva o produto em linguagem natural. Nossa IA sugere o NCM correto,
            o cClassTrib da LC 214 e as alíquotas CBS/IBS aplicáveis em segundos.
          </p>
          <div className="mx-auto mt-2 flex flex-wrap items-center justify-center gap-4 text-sm text-slate-400">
            <span>10 classificações gratuitas/dia</span>
            <span>·</span>
            <span>Sem login</span>
            <span>·</span>
            <span>LC 214 · NT 2025.002 v1.36</span>
          </div>
        </div>
      </section>

      {/* Widget interativo */}
      <section className="mx-auto -mt-6 max-w-2xl px-4 pb-12">
        <Classifier />
      </section>

      {/* SSR explanatory content */}
      <section className="border-t border-slate-200 bg-white py-12">
        <div className="mx-auto max-w-3xl px-4 space-y-10">
          <div>
            <h2 className="mb-3 text-2xl font-bold text-slate-900">O que é o cClassTrib</h2>
            <p className="text-slate-700">
              O <strong>cClassTrib</strong> (Código de Classificação Tributária) é um código numérico
              de 6 dígitos introduzido pela <strong>Lei Complementar 214/2025</strong> e detalhado pela
              <strong> Nota Técnica 2025.002-RTC</strong>. Ele define o regime tributário de IBS e CBS
              aplicável a cada item da NF-e — informa à SEFAZ se o produto é normalmente tributado,
              tem alíquota reduzida, integra a cesta básica, está sujeito a monofásico, é imune ou
              suspenso.
            </p>
            <p className="mt-3 text-slate-700">
              O cClassTrib vive no XML da NF-e dentro do grupo <code className="rounded bg-slate-100 px-1 font-mono text-sm">gIBSCBS</code> ou
              <code className="rounded bg-slate-100 px-1 font-mono text-sm"> gIBSCBSMono</code>, ao
              lado do CST. A SEFAZ valida em tempo real se o cClassTrib é compatível com o CST
              informado — quando há descasamento, a nota é rejeitada com o código <strong>1024</strong>.
            </p>
          </div>

          <div>
            <h2 className="mb-3 text-2xl font-bold text-slate-900">Estrutura do código cClassTrib</h2>
            <p className="text-slate-700">
              Os 6 dígitos do cClassTrib têm semântica posicional. Os três primeiros dígitos batem
              obrigatoriamente com o CST informado — esta é a fonte mais comum de Rejeição 1024:
            </p>
            <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">Posição</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">Significado</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">Exemplo</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-slate-100">
                    <td className="px-4 py-2 font-mono">1-3</td>
                    <td className="px-4 py-2">Espelha o CST do item (vínculo obrigatório)</td>
                    <td className="px-4 py-2 font-mono">000, 011, 200, 400, 410, 510, 620…</td>
                  </tr>
                  <tr className="border-t border-slate-100">
                    <td className="px-4 py-2 font-mono">4-6</td>
                    <td className="px-4 py-2">Sequencial da situação tributária dentro daquele CST</td>
                    <td className="px-4 py-2 font-mono">001, 002, 003…</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-sm text-slate-600">
              Exemplo: <code className="rounded bg-slate-100 px-1 font-mono">{CLASSTRIB_CESTA_BASICA}</code> indica
              CST 200 (alíquota reduzida) + sequencial 003 — na tabela oficial SVRS, vendas de
              produtos destinados à alimentação humana relacionados no Anexo I da LC 214/2025.
              Se o CST do item for diferente de 200, a nota é rejeitada (1024).
            </p>
          </div>

          <div>
            <h2 className="mb-3 text-2xl font-bold text-slate-900">Por que o NCM sozinho não basta</h2>
            <p className="text-slate-700">
              Um mesmo NCM pode ter múltiplos cClassTrib válidos dependendo do regime de operação,
              do destinatário e da localização. A automação é uma armadilha clássica: ERPs que
              parametrizam um cClassTrib fixo por NCM funcionam para o caso médio mas falham nos
              casos especiais — exatamente as operações com maior risco fiscal.
            </p>
            <p className="mt-3 text-slate-700">
              Exemplos onde o mesmo NCM exige cClassTribs diferentes:
            </p>
            <ul className="mt-3 list-disc space-y-2 pl-6 text-slate-700">
              <li><strong>Medicamentos (NCM 3004)</strong>: alíquota zero para uso humano vs. tributação normal para uso veterinário.</li>
              <li><strong>Alimentos básicos (NCM 1001-1006)</strong>: cesta básica nacional vs. cesta básica estadual diferenciada.</li>
              <li><strong>Combustíveis (NCM 2710)</strong>: monofásico (CST 620) para distribuidores vs. tributação normal para outros usos.</li>
              <li><strong>Bebidas (NCM 2202)</strong>: Substituição Tributária para refrigerantes vs. tributação normal para sucos.</li>
            </ul>
          </div>

          <div>
            <h2 className="mb-3 text-2xl font-bold text-slate-900">Cenários mais comuns da Rejeição 1024</h2>
            <p className="text-slate-700">
              A Rejeição 1024 acontece quando a SEFAZ detecta que o cClassTrib informado é
              incompatível com o CST do item. Os três cenários mais frequentes vistos em
              produção desde janeiro/2026:
            </p>
            <ol className="mt-3 list-decimal space-y-3 pl-6 text-slate-700">
              <li>
                <strong>ERP ativou IBS/CBS com cClassTrib genérico (000001) para tudo.</strong>
                Funciona para CST 000 normal, mas qualquer item com CST 070 (imune) ou 200 (diferimento) gera rejeição.
              </li>
              <li>
                <strong>NCM com múltiplos cClassTribs e o sistema escolhe o primeiro.</strong>
                Tipicamente em medicamentos, alimentos e produtos químicos — o critério deveria ser o uso ou destino, não a ordem da tabela.
              </li>
              <li>
                <strong>Alíquota parametrizada como zero ou calculada dinamicamente.</strong>
                Quando o vCBS ou vIBS sai como 0,00 sem o cClassTrib informar isenção (CST 070) ou suspensão (410), a validação cruzada detecta e rejeita.
              </li>
            </ol>
          </div>

          <div>
            <h2 className="mb-3 text-2xl font-bold text-slate-900">Como o Tribultz automatiza a classificação</h2>
            <p className="text-slate-700">
              A Tribultz combina três fontes para sugerir o cClassTrib correto:
            </p>
            <ul className="mt-3 list-disc space-y-2 pl-6 text-slate-700">
              <li>Base oficial cClassTrib da SVRS (tabela da NT 2025.002-RTC v1.40)</li>
              <li>Anexos da LC 214 com regime, alíquota referência e vigência por NCM</li>
              <li>Modelo de IA treinado sobre descrições reais de NF-e para resolver ambiguidade do NCM a partir da descrição em linguagem natural</li>
            </ul>
            <p className="mt-3 text-slate-700">
              O resultado é entregue com indicador de confiança e link direto para a calculadora
              CBS/IBS. Para casos críticos (confiança &lt; {CONFIANCA_MINIMA_PCT}%, regimes especiais, exportação),
              recomendamos validação manual antes de transmitir a NF-e.
            </p>

            {/* #660: régua visível, derivada da fonte única. Antes os limiares só
                apareciam soltos em resposta de FAQ — quem lia a página não tinha
                onde consultar o que cada faixa significa. */}
            <div className="mt-5 overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-sm">
                <caption className="px-4 pt-3 text-left text-sm font-semibold text-slate-900">
                  Como ler o indicador de confiança
                </caption>
                <thead className="bg-slate-50">
                  <tr>
                    <th scope="col" className="px-4 py-2 text-left font-semibold text-slate-700">Confiança</th>
                    <th scope="col" className="px-4 py-2 text-left font-semibold text-slate-700">O que fazer</th>
                  </tr>
                </thead>
                <tbody>
                  {REGUA_CONFIANCA.map((f) => (
                    <tr key={f.faixa} className="border-t border-slate-100">
                      <td className="whitespace-nowrap px-4 py-2 font-mono">{f.rotulo}</td>
                      <td className="px-4 py-2 text-slate-700">{f.acao}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
