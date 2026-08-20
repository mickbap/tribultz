/**
 * Guards do consentimento de cookies — conformidade com o Guia Orientativo da
 * ANPD ("Cookies e Proteção de Dados Pessoais", out/2022).
 *
 * O defeito que originou estes testes: o banner informava apenas cookies de
 * análise, e o código concedia TAMBÉM `ad_storage`, `ad_user_data` e
 * `ad_personalization` — consentimento fora do escopo informado, em dois
 * lugares (lib/consent.ts e o bloco de restauração do layout).
 *
 * Guard de texto-fonte é proposital: o bloco do layout é uma string de script
 * injetada no HTML, então não há como exercitá-lo por import. A regressão que
 * queremos impedir é alguém reintroduzir a concessão de sinal de publicidade.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const ler = (rel: string) => readFileSync(join(raiz, rel), "utf8");

const SINAIS_DE_PUBLICIDADE = ["ad_storage", "ad_user_data", "ad_personalization"];

type Chamada = { args: unknown[] };

function comJanela(inicial: string | null, corpo: (chamadas: Chamada[]) => void) {
  const store = new Map<string, string>();
  if (inicial !== null) store.set("tribultz-cookie-consent", inicial);
  const chamadas: Chamada[] = [];
  (globalThis as Record<string, unknown>).window = {
    localStorage: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    },
    gtag: (...args: unknown[]) => void chamadas.push({ args }),
  };
  try {
    corpo(chamadas);
  } finally {
    delete (globalThis as Record<string, unknown>).window;
  }
}

test("setConsent nunca concede sinal de publicidade, em nenhuma escolha", async () => {
  const { setConsent, CONSENT_TOTAL, CONSENT_NEGADO } = await import("./consent.ts");
  for (const escolha of [CONSENT_TOTAL, CONSENT_NEGADO]) {
    comJanela(null, (chamadas) => {
      setConsent(escolha);
      const emitido = JSON.stringify(chamadas);
      for (const sinal of SINAIS_DE_PUBLICIDADE) {
        assert.ok(
          !emitido.includes(sinal),
          `setConsent(${JSON.stringify(escolha)}) emitiu ${sinal} — o banner não informa publicidade`,
        );
      }
    });
  }
});

test("aceitar análise concede analytics_storage; recusar mantém negado", async () => {
  const { setConsent } = await import("./consent.ts");
  comJanela(null, (chamadas) => {
    setConsent({ analise: true });
    assert.match(JSON.stringify(chamadas), /"analytics_storage":"granted"/);
  });
  comJanela(null, (chamadas) => {
    setConsent({ analise: false });
    assert.match(JSON.stringify(chamadas), /"analytics_storage":"denied"/);
  });
});

test("consentimento de versão anterior equivale a não ter decidido", async () => {
  const { getStoredConsent, CONSENT_POLICY_VERSION } = await import("./consent.ts");
  // ANPD: "qualquer alteração das premissas adotadas para a obtenção do
  // consentimento macula a hipótese legal adotada, exigindo novo consentimento".
  const antigo = JSON.stringify({ analise: true, version: "1999-01-01", decidedAt: "x" });
  comJanela(antigo, () => assert.equal(getStoredConsent(), null));

  const atual = JSON.stringify({
    analise: true,
    version: CONSENT_POLICY_VERSION,
    decidedAt: "x",
  });
  comJanela(atual, () => assert.equal(getStoredConsent()?.analise, true));
});

test("formato legado (string 'granted') não é aceito como consentimento", async () => {
  const { getStoredConsent } = await import("./consent.ts");
  // Aquele "granted" foi dado sob um banner que informava só análise enquanto
  // concedia publicidade. Não vale para as premissas atuais.
  comJanela("granted", () => assert.equal(getStoredConsent(), null));
});

test("revogação apaga o registro e volta a negar (art. 8º §5º)", async () => {
  const { revokeConsent, getStoredConsent, CONSENT_POLICY_VERSION } = await import("./consent.ts");
  const atual = JSON.stringify({
    analise: true,
    version: CONSENT_POLICY_VERSION,
    decidedAt: "x",
  });
  comJanela(atual, (chamadas) => {
    revokeConsent();
    assert.equal(getStoredConsent(), null);
    assert.match(JSON.stringify(chamadas), /"analytics_storage":"denied"/);
  });
});

test("o bloco de restauração do layout não concede publicidade", () => {
  const layout = ler("app/layout.tsx");
  const restauracao = layout.slice(layout.indexOf("consent', 'default'"));
  for (const sinal of SINAIS_DE_PUBLICIDADE) {
    assert.ok(
      !restauracao.includes(`${sinal}: 'granted'`),
      `layout.tsx restaura ${sinal} como granted — regressão do defeito original`,
    );
  }
  assert.ok(
    layout.includes("c.version === '${CONSENT_POLICY_VERSION}'"),
    "a restauração precisa conferir a versão da política antes de reaplicar a escolha",
  );
});

test("o default do Consent Mode nega os quatro sinais antes do gtag.js", () => {
  const layout = ler("app/layout.tsx");
  const bloco = layout.slice(
    layout.indexOf("consent', 'default'"),
    layout.indexOf("Google tag (gtag.js)"),
  );
  for (const sinal of [...SINAIS_DE_PUBLICIDADE, "analytics_storage"]) {
    assert.ok(bloco.includes(`${sinal}: 'denied'`), `${sinal} precisa começar negado`);
  }
  assert.ok(
    layout.indexOf('id="ga-consent-default"') < layout.indexOf('id="ga-loader"'),
    "o default precisa ser declarado antes do carregamento do gtag.js",
  );
});

test("o banner oferece as três ações exigidas pela ANPD, com o mesmo estilo", () => {
  const arquivo = ler("components/common/CookieConsent.tsx");
  // Só o JSX conta: o comentário do topo cita os mesmos rótulos, e um guard que
  // aceitasse a citação passaria verde com o botão removido (provado quebrando).
  const banner = arquivo.slice(arquivo.indexOf("return ("));
  for (const rotulo of [
    "Rejeitar cookies não necessários",
    "Aceitar todos os cookies",
    "Selecionar cookies",
  ]) {
    // O rótulo tem que ser CONTEÚDO de botão. (`<button[^>]*>` não serve:
    // `onClick={() => ...}` tem `>` dentro do atributo e a classe para cedo.)
    assert.ok(
      new RegExp(`${rotulo}\\s*</button>`).test(banner),
      `banner sem a ação "${rotulo}" dentro de um <button>`,
    );
  }
  // Mesmo destaque: as três usam a mesma classe. O guia rejeita o padrão em que
  // aceitar é botão e recusar é link apagado.
  const classes = [...banner.matchAll(/className=\{botao\}/g)];
  assert.ok(classes.length >= 3, "as ações do banner precisam do mesmo tratamento visual");
});

test("a categoria de análise começa desativada (sem opção pré-selecionada)", () => {
  const banner = ler("components/common/CookieConsent.tsx");
  // Precisa nomear a variável: há outros useState(false) no componente, e o
  // guard genérico passava verde com a caixa pré-marcada (provado quebrando).
  assert.ok(
    banner.includes("const [analise, setAnalise] = useState(false)"),
    "a categoria opcional precisa iniciar desmarcada",
  );
  assert.ok(
    !banner.includes("defaultChecked"),
    "nenhuma caixa pode vir pré-marcada — vedado pelo guia da ANPD",
  );
});

test("a política de cookies traz inventário com finalidade, duração e origem", () => {
  const pagina = ler("app/cookies/page.tsx");
  for (const coluna of ["Nome", "Categoria", "Finalidade", "Duração", "Origem"]) {
    assert.ok(pagina.includes(`>${coluna}<`), `inventário sem a coluna "${coluna}"`);
  }
  assert.ok(pagina.includes("_ga"), "o inventário precisa nomear os cookies de análise");
});
