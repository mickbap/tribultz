/**
 * Guards de sabotagem editorial (ROUND BLOG 30/08-E, Fase 9).
 *
 * Escopo: artigos INDEXÁVEIS. Artigo contido está fora do índice e ainda
 * carrega os claims que a auditoria jurídica reprovou — barrá-lo aqui
 * confundiria "contido aguardando reescrita" com "publicado e errado", e
 * vermelharia o CI justamente enquanto a correção é feita.
 *
 * Cada guard corresponde a uma letra da Fase 9 da ordem.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { MARCADOR_NAO_DETERMINADO } from "../components/seo/ProvenienciaClaims";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const dir = join(raiz, "content", "blog");
const ler = (f: string) => readFileSync(join(dir, f), "utf8");
const arquivos = readdirSync(dir).filter((f) => f.endsWith(".mdx"));
const contido = (s: string) => /^noindex:\s*true\s*$/m.test(/^---\n([\s\S]*?)\n---/.exec(s)?.[1] ?? "");
const indexaveis = arquivos.filter((f) => !contido(ler(f)));
const corpo = (s: string) => s.replace(/^---\n[\s\S]*?\n---/, "").replace(/<[^>]*>/g, " ");
const um = (slug: string) => ler(`${slug}.mdx`);

// ── A/B/C — Rejeição 960 ────────────────────────────────────────────────────
/**
 * Os guards encodam as EXPRESSÕES PROIBIDAS do pacote editorial, não uma
 * redação específica. Exigir o token "não" em toda frase reprovava negações
 * legítimas ("são problemas diferentes") e aprovaria uma afirmação proibida
 * que contivesse um "não" acidental em outro ponto da frase.
 */
const NEGA_960 = /\bn[ãa]o\b|\bnem\b|\bsem\b|diferente|distint|separad|pr[óo]pri|outros? (dom[íi]nios?|grupos?)/i;
const frases = (t: string) => [...t.matchAll(/[^.]+\./g)].map((m) => m[0]);

test("A: 960 não volta a ser associada a cClassTrib", () => {
  const t = corpo(um("rejeicao-960-nf-e"));
  // Proibido: "960 é erro de cClassTrib" / "cClassTrib ausente causa 960".
  const liga = /\b(é|e|significa|ocorre|decorre|causa|gera|resulta|valida|verifica|indica)\b/i;
  for (const f of frases(t)) {
    if (!/cClassTrib/.test(f)) continue;
    if (!/\b960\b|N12-110/.test(f)) continue;
    assert.match(f, NEGA_960, `960 associada a cClassTrib sem separação explícita: "${f.trim()}"`);
    void liga;
  }
});

test("B: 960 usa v1.60 como versão corrente, nunca v1.51 da NT 2023.001", () => {
  const s = um("rejeicao-960-nf-e");
  assert.match(s, /artifact:\s*"NT 2023\.001[^"]*"[\s\S]{0,120}?artifact_version:\s*"1\.60/);
  assert.ok(
    !/NT 2023\.001[^\n]{0,40}v\.?1\.51/.test(s),
    "v1.51 é histórica da NT 2023.001 — não pode voltar como corrente",
  );
});

test("C: 960 registra a exceção corrente finNFe=5/6", () => {
  const s = um("rejeicao-960-nf-e");
  assert.match(corpo(s), /finNFe=5/, "corpo precisa registrar a exceção NF-e de Crédito");
  assert.match(corpo(s), /finNFe=6/, "corpo precisa registrar a exceção NF-e de Débito");
  // A exceção precisa de claim próprio, ancorado na documentação que a criou.
  assert.match(
    s,
    /claim_scope:[^\n]*finNFe[\s\S]{0,400}?artifact:\s*"NT 2025\.002-RTC/,
    "a exceção finNFe=5/6 precisa de claim próprio na documentação RTC",
  );
});

test("960: sem RTC como origem e sem 03/08/2026", () => {
  const t = corpo(um("rejeicao-960-nf-e"));
  assert.ok(!/03\/08\/2026|03\/08/.test(t), "960 não tem relação com 03/08/2026");
  // Proibido: "a Rejeição 960 surgiu com a Reforma Tributária".
  const origem = /surgiu|nasceu|origem|criada|introduzid|pertence|deriv|vem d/i;
  for (const f of frases(t)) {
    if (!/Reforma Tribut|\bRTC\b/i.test(f)) continue;
    if (!/\b960\b|N12-110/.test(f)) continue;
    if (!origem.test(f)) continue;
    assert.match(f, NEGA_960, `960 associada à RTC como origem: "${f.trim()}"`);
  }
});

test("960: nenhuma lista fixa de cProdANP sem proveniência versionada", () => {
  const s = um("rejeicao-960-nf-e");
  const t = corpo(s);
  // Uma lista de códigos ANP no corpo só se admite com claim versionado da tabela.
  const listaAnp = /cProdANP[^.]{0,80}(\d{6,}\s*[,;]\s*){2,}/i;
  assert.ok(!listaAnp.test(t), "lista fixa de cProdANP reproduzida no corpo");
  assert.match(
    s,
    /artifact:\s*"Tabela de Combust[íi]veis Sujeitos [àa] Tributa[çc][ãa]o Monof[áa]sica"/,
    "a tabela de combustíveis precisa de claim próprio",
  );
});

// ── D — Rejeição 1024 ───────────────────────────────────────────────────────
test("D: artigo indexável não republica tabela de cStats sem contrato", () => {
  for (const f of indexaveis) {
    const t = corpo(ler(f));
    for (const c of ["1025", "1026", "1027", "1029", "1030"]) {
      assert.ok(!new RegExp(`\\b${c}\\b`).test(t), `${f} cita cStat ${c} sem contrato individual`);
    }
  }
});

// ── E/F/G — NCM ─────────────────────────────────────────────────────────────
test("E/F/G: artigo indexável não faz NCM determinar cClassTrib, CST ou benefício", () => {
  const proibidos: Array<[RegExp, string]> = [
    [/NCM\s+(determina|define)\s+o\s+cClassTrib/i, "NCM → cClassTrib unívoco"],
    [/de-para\s+(universal\s+)?(de\s+)?NCM/i, "de-para universal de NCM"],
    [/NCM\s+(determina|define)\s+o\s+CST/i, "NCM → CST definitivo"],
    [/NCM[^.]{0,60}benefício\s+autom/i, "NCM → benefício automático"],
    [/[Ss]ugest[ãa]o[^.]{0,40}\b(certificad\w*|garante|garantem|determina|determinam|confirma|comprova)\b/i, "CFF Sugestão como classificação certificada"],
  ];
  for (const f of indexaveis) {
    const t = corpo(ler(f));
    for (const [rx, oque] of proibidos) {
      assert.ok(!rx.test(t), `${f}: ${oque}`);
    }
  }
});

// ── H/I — RGI e INs ─────────────────────────────────────────────────────────
test("H/I: artigo indexável não inverte RGI 3b/3c nem cita IN RFB 1.799/2018", () => {
  for (const f of indexaveis) {
    const t = corpo(ler(f));
    // O texto aprovado usa "RGI 3(b)"; a redação anterior usava "RGI 3b".
    // O guard precisa cobrir as duas notações, senão deixa de proteger.
    assert.ok(!/RGI\s*3\s*\(?\s*b\s*\)?[^.]{0,40}(maior valor|mais específic)/i.test(t), `${f}: RGI 3b incorreta`);
    assert.ok(!/RGI\s*3\s*\(?\s*c\s*\)?[^.]{0,40}mais específic/i.test(t), `${f}: RGI 3c incorreta`);
    assert.ok(!/1\.799\/2018|1799\/2018/.test(t), `${f}: IN RFB 1.799/2018 como norma do procedimento`);
  }
});

// ── J — alíquotas ───────────────────────────────────────────────────────────
/**
 * A exceção ALIQUOTA_DEFEITO_VIVO_2026_08_30 foi REMOVIDA em 30/08/2026, com a
 * reescrita de `como-calcular-aliquota-cbs-ibs` no ROUND BLOG 30/08-E. O guard
 * volta a valer para todo artigo indexável, sem lista de dispensa.
 */
test("J: artigo indexável não apresenta estimativa futura como alíquota normativa", () => {
  for (const f of indexaveis) {
    const t = corpo(ler(f));
    for (const m of t.matchAll(/[^.]*\b(8,8|17,7|26,5)\s?%[^.]*\./g)) {
      assert.match(
        m[0],
        // Mesmo conjunto do guard Y: marcação de estimativa OU repúdio
        // explícito da formulação normativa contam como marcação.
        /estimativ|proje[çc]|simula[çc]|hist[óo]ric|refer[êe]ncia|n[ãa]o\s+fixad|n[ãa]o devem?\b|aguard/i,
        `${f}: percentual futuro sem marcação de estimativa: "${m[0].trim().slice(0, 120)}"`,
      );
    }
  }
});

// ── K — 03/08 ───────────────────────────────────────────────────────────────
test("K: artigo indexável não converte obrigação documental em rejeição automática", () => {
  for (const f of indexaveis) {
    const t = corpo(ler(f));
    assert.ok(
      !/(desde|a partir de)\s+03\/08[^.]{0,80}rejeit/i.test(t) &&
        !/rejeit[^.]{0,80}(desde|a partir de)\s+03\/08/i.test(t),
      `${f}: equipara obrigação documental a rejeição automática desde 03/08`,
    );
  }
});

// ── L/M — 1115 e 1119 ───────────────────────────────────────────────────────
test("L/M: 1115 com produção futura; 1119 sem data exata de ativação", () => {
  for (const f of indexaveis) {
    const s = ler(f);
    const t = corpo(s);
    if (/\b1115\b/.test(t) && /UB12-10/.test(s)) {
      assert.match(s, /temporal_applicability:[^\n]*futur/i, `${f}: 1115 sem produção futura declarada`);
    }
    if (/W34-20/.test(s)) {
      assert.ok(
        /NAO_DETERMINADO|não\s+determinad/i.test(s),
        `${f}: 1119/W34-20 precisa declarar que a data de ativação não está determinada`,
      );
    }
  }
});

// ── N — NAO_DETERMINADO ─────────────────────────────────────────────────────
test("N: NAO_DETERMINADO tem rótulo próprio e distinto de fato na renderização", () => {
  const comp = readFileSync(join(raiz, "src", "components", "seo", "ProvenienciaClaims.tsx"), "utf8");
  assert.ok(comp.includes("MARCADOR_NAO_DETERMINADO"));
  assert.notEqual(MARCADOR_NAO_DETERMINADO, "Fato normativo");
  // A renderização ramifica na classificação — não existe caminho que
  // apresente uma natureza sob o rótulo de outra.
  assert.match(comp, /ROTULO\[c\.claim_classification\]/);
  assert.match(comp, /data-classification=\{c\.claim_classification\}/);
  // E a página do post usa este componente, não uma renderização paralela.
  const page = readFileSync(join(raiz, "src", "app", "blog", "[slug]", "page.tsx"), "utf8");
  assert.ok(page.includes("ProvenienciaClaims"), "a página precisa renderizar por este caminho");
});

// ── P0 do ROUND BLOG 30/08 — não regredir ───────────────────────────────────
/**
 * Os sete P0 da auditoria de 30/08/2026, todos reindexados com baseline
 * editorial aprovado. O sétimo foi reindexado sem resolver a divergência
 * sobre a produção da UB12-10: ele não afirma data de ativação, e a
 * divergência vive na proveniência do claim — ver o guard logo abaixo.
 */
test("P0: indexado exige META_TITLE e proveniência limpa; contido exige motivo", () => {
  const P0 = [
    "rejeicao-960-nf-e",
    "rejeicao-1024-nfe-cbs-ibs-como-corrigir",
    "classtrib-2026-mapear-ncm-regime-ibs-cbs",
    "classtrib-2026-ncm-mapeamento-completo",
    "como-classificar-ncm-corretamente-2026",
    "como-calcular-aliquota-cbs-ibs",
    "nfe-rejeitada-03-08-2026-regime-normal-crt3",
  ];
  for (const slug of P0) {
    const s = um(slug);
    assert.match(s, /^provenance:$/m, `${slug}: sem bloco provenance`);
    assert.match(s, /^metaTitle:\s*"[^"]+"/m, `${slug}: META_TITLE aprovado ausente`);
    const bloqueado = /provenance_blocked:\s*true/.test(s);
    if (contido(s)) {
      assert.match(s, /^noindexReason:\s*"[^"]+"/m, `${slug}: contido sem motivo declarado`);
    } else {
      // Indexar com claim sem fonte oficial seria transformar autorização
      // jurídica em bypass técnico — que é exatamente o que a ordem proíbe.
      assert.ok(!bloqueado, `${slug}: indexado com claim PROVENANCE_BLOCKED`);
    }
    // Um claim bloqueado nunca pode ter sido apagado para destravar o artigo.
    if (bloqueado) {
      assert.match(s, /blocked_reason:\s*"[^"]+"/, `${slug}: bloqueio sem razão registrada`);
      assert.ok(contido(s), `${slug}: claim bloqueado obriga contenção`);
    }
  }
});
test("UB12-10: estado presente determinado, data futura não determinada", () => {
  const arq = "nfe-rejeitada-03-08-2026-regime-normal-crt3";
  const s = um(arq);
  const t = corpo(s);
  // Varredura por LINHA: em MDX cada parágrafo e cada linha de tabela é uma
  // unidade. Dividir por ponto quebraria linhas de tabela ao meio e acusaria
  // a pergunta sem enxergar a resposta na mesma linha.
  const linhas = t.split("\n").filter((l) => l.trim());
  const nega = (l: string) => /\bn[ãa]o\b|postergou|adiad|implementação futura/i.test(l);

  // 1 — não afirmar que a regra está ativa em produção
  for (const l of linhas) {
    if (/(UB12-10|\b1115\b)/.test(l) && /ativa\s+em\s+produção|em\s+produção\s+desde/i.test(l)) {
      assert.ok(nega(l), `afirma UB12-10 ativa em produção: "${l.slice(0, 140)}"`);
    }
  }

  // 2 — 03/08/2026 não pode ser apresentado como data corrente de ativação
  for (const l of linhas) {
    if (/03\/08\/2026/.test(l) && /ativa|ativação|vigora|passou a valer/i.test(l)) {
      assert.match(l, /previsão histórica|históric|postergou|prevista|\bn[ãa]o\b/i,
        `03/08/2026 como data corrente de ativação: "${l.slice(0, 140)}"`);
    }
  }

  // 3 — nenhuma nova data futura de ativação
  for (const l of linhas) {
    assert.doesNotMatch(l, /(nova data|data de ativação|volta a ser aplicad\w*|ser[áa] ativad\w*)[^.]{0,60}\d{2}\/\d{2}\/\d{4}/i,
      `afirma nova data de ativação: "${l.slice(0, 140)}"`);
  }

  // 4 — o adiamento não suspende a obrigação documental
  for (const l of linhas) {
    if (/adiamento|adiada|postergou|postergaç/i.test(l) && /suspend|dispens|afast/i.test(l)) {
      assert.match(l, /\bn[ãa]o\b/i, `adiamento tratado como dispensa da obrigação: "${l.slice(0, 140)}"`);
    }
  }

  // 5 — ausência dos campos não gera 1115 automático em produção hoje
  for (const l of linhas) {
    if (/aus[êe]ncia|não informado/i.test(l) && /\b1115\b|rejeição automática/i.test(l) && /produção/i.test(l)) {
      assert.match(l, /\bn[ãa]o\b/i, `afirma 1115 automático em produção: "${l.slice(0, 140)}"`);
    }
  }

  // 6/7 — as duas classificações, lidas da estrutura e não da prosa
  const blocos = (/^provenance:\n([\s\S]*?)(?=^\w|\n---)/m.exec(s)?.[1] ?? "").split(/\n  - /).filter(Boolean);
  const acha = (rx: RegExp) => blocos.find((b) => rx.test(b));
  const classe = (b?: string) => /claim_classification: "([A-Z_]+)"/.exec(b ?? "")?.[1];

  const estadoAtual = acha(/em produção está adiada|implementação futura para produção/i);
  assert.ok(estadoAtual, "sem claim do ESTADO ATUAL da UB12-10");
  assert.equal(classe(estadoAtual), "FATO_NORMATIVO",
    "o estado presente está determinado pela fonte — não pode ser NAO_DETERMINADO");

  const dataFutura = acha(/A partir de qual data a regra UB12-10/i);
  assert.ok(dataFutura, "sem claim da DATA FUTURA de ativação");
  assert.equal(classe(dataFutura), "NAO_DETERMINADO",
    "a data futura só vira fato com nova fonte oficial posterior");

  // A nota de versionamento é proveniência temporal, não conflito irresolvido.
  assert.match(s, /versioning_note: "Nota de versionamento:/,
    "a linhagem de versões precisa estar declarada como versionamento");

  // 8 — 03/08/2026 permanece na linhagem histórica
  assert.match(t, /03\/08\/2026/, "03/08/2026 não pode sumir: é a previsão histórica da regra");
});

// ── R–W — regressões materiais do ROUND BLOG 30/08-I ────────────────────────
/**
 * Guards de forma, não de frase. Cada um descreve o FORMATO da afirmação
 * proibida (sujeito + verbo + objeto, com sinônimos), porque a mesma regressão
 * reaparece com redação trivialmente diferente e um guard de frase exata só
 * pegaria a redação que já conhecíamos.
 *
 * A janela é a linha mais a próxima linha não vazia: em FAQ, a pergunta e a
 * resposta são linhas distintas, e é a resposta que carrega a negação.
 */
type Janela = { alvo: string; contexto: string };
function janelas(t: string): Janela[] {
  const l = t.split("\n").map((x) => x.trim()).filter(Boolean);
  // O gatilho é procurado em `alvo` (uma linha só). A negação é aceita em
  // `contexto` (a linha e a seguinte), porque em FAQ a resposta vem depois.
  // Sem essa separação, a janela de uma resposta engoliria a pergunta
  // seguinte e acusaria um gatilho cuja negação está duas linhas adiante.
  // A linha SEGUINTE sempre entra: em FAQ, a resposta que nega vem depois.
  // A ANTERIOR só entra quando termina em dois-pontos, isto é, quando ela
  // INTRODUZ o alvo ("não é seguro programar:" seguido do exemplo). Sem essa
  // restrição, um "não" de uma frase vizinha e sem relação isentaria o alvo —
  // foi assim que uma sabotagem de split payment passou.
  return l.map((linha, i) => {
    const prev = l[i - 1] ?? "";
    const introduz = /[:;]\s*$/.test(prev);
    return { alvo: linha, contexto: `${introduz ? prev : ""} ${linha} ${l[i + 1] ?? ""}` };
  });
}
const NEGA = /\bn[ãa]o\b|\bnem\b|\bjamais\b|\bsem que\b|\bao contr[áa]rio\b/i;

test("R: 1024 não é atribuída a ausência de grupo, alíquota ou diferimento", () => {
  const causas: Array<[RegExp, string]> = [
    [/aus[êe]ncia|ausente|n[ãa]o informad|n[ãa]o preenchid|falta d\w+/i, "ausência do grupo"],
    [/al[íi]quota\s+(incorreta|errada|divergente)|erro de al[íi]quota/i, "alíquota incorreta"],
    [/diferimento/i, "diferimento"],
  ];
  for (const f of indexaveis) {
    for (const { alvo: j, contexto: ctx } of janelas(corpo(ler(f)))) {
      if (!/\b1024\b/.test(j)) continue;
      for (const [rx, oque] of causas) {
        if (rx.test(j) && !NEGA.test(ctx)) {
          assert.fail(`${f}: 1024 atribuída a ${oque} — "${j.slice(0, 150)}"`);
        }
      }
    }
  }
});

test("S: ausência do NCM nos anexos não determina CST nem cClassTrib", () => {
  const fora = /(fora|n[ãa]o cons\w+|n[ãa]o aparec\w+|n[ãa]o est\w+|aus[êe]ncia|ausente)[^.]{0,40}anexos?/i;
  const conclui = /CST\s*0?00\b|tributaç[ãa]o integral|regime (geral|padr[ãa]o)/i;
  // Aqui a negação genérica não serve: em "se o NCM NÃO consta do anexo,
  // aplica-se o CST 000" o "não" nega a CONDIÇÃO e a conclusão segue afirmada.
  // Só isenta a negação da própria consequência.
  const NEGA_CONSEQ = /n[ãa]o\s+(determina|implica|significa|autoriza|permite|conclui|leva|equivale|define|prova|deve|[ée] seguro)/i;
  for (const f of indexaveis) {
    for (const { alvo: j, contexto: ctx } of janelas(corpo(ler(f)))) {
      if (fora.test(j) && conclui.test(j) && !NEGA_CONSEQ.test(ctx)) {
        assert.fail(`${f}: ausência no anexo tratada como determinante — "${j.slice(0, 150)}"`);
      }
    }
  }
});

test("X: mecânica de split payment exige contrato normativo próprio", () => {
  const mecanica = /split\s*payment|pagamento\s+dividido/i;
  const afirmaEfeito = /ret[êe]m|retenç|retid|liquidaç|banco|autom[áa]tic|recolhiment|deduz/i;
  for (const f of indexaveis) {
    const s = ler(f);
    const fm = /^---\n([\s\S]*?)\n---/.exec(s)?.[1] ?? "";
    // Contrato = um claim de proveniência que fale de split payment e nomeie
    // artefato. Sem isso, descrever o mecanismo é afirmar norma sem fonte.
    const temContrato = /(claim_scope|rule_item):[^\n]*split/i.test(fm);
    for (const { alvo: j, contexto: ctx } of janelas(corpo(s))) {
      // Negar que o domínio se aplica não é descrever o mecanismo.
      if (mecanica.test(j) && afirmaEfeito.test(ctx) && !NEGA.test(ctx) && !temContrato) {
        assert.fail(`${f}: descreve efeito de split payment sem claim de proveniência próprio — "${j.slice(0, 140)}"`);
      }
    }
  }
});

test("T: CEST não é apresentado como causa da Rejeição 1024", () => {
  for (const f of indexaveis) {
    for (const { alvo: j, contexto: ctx } of janelas(corpo(ler(f)))) {
      if (/\bCEST\b/.test(j) && /\b1024\b/.test(j) && !NEGA.test(ctx)) {
        assert.fail(`${f}: CEST ligado à 1024 — "${j.slice(0, 150)}"`);
      }
    }
  }
});

test("U: não se afirma recolhimento universal nem carga única em 2026", () => {
  const universal = /\b(todo|toda|todos|todas|qualquer)\s+(os\s+|as\s+|o\s+|a\s+)?(contribuinte|empresa|emitente|neg[óo]cio)\w*/i;
  const recolhe = /\brecolh\w+|\bpag\w+\b|\bdev\w+\s+\d/i;
  for (const f of indexaveis) {
    for (const { alvo: j, contexto: ctx } of janelas(corpo(ler(f)))) {
      if (universal.test(j) && recolhe.test(j) && /\b2026\b|\b1\s?%|0,9|0,1/.test(j) && !NEGA.test(ctx)) {
        assert.fail(`${f}: recolhimento universal afirmado — "${j.slice(0, 150)}"`);
      }
      // A soma 0,9 + 0,1 apresentada como carga de todos.
      if (/\b1\s?%/.test(j) && /\b2026\b/.test(j) && /carga|al[íi]quota total|som\w+/i.test(j) && !NEGA.test(ctx)) {
        assert.fail(`${f}: 1% em 2026 como carga geral — "${j.slice(0, 150)}"`);
      }
    }
  }
});

test("V: compatibilidade entre campos não é apresentada como operação correta", () => {
  const compat = /compat[íi]v\w+|compatibilidade|coerent\w+|combinaç[ãa]o v[áa]lida/i;
  const conclui = /operaç[ãa]o\s+(est[áa]\s+)?(correta|regular)|incid[êe]ncia correta|tributaç[ãa]o correta|necessariamente correta/i;
  for (const f of indexaveis) {
    for (const { alvo: j, contexto: ctx } of janelas(corpo(ler(f)))) {
      if (compat.test(j) && conclui.test(j) && !NEGA.test(ctx)) {
        assert.fail(`${f}: campos compatíveis tratados como operação correta — "${j.slice(0, 150)}"`);
      }
    }
  }
});

test("W: nenhuma promessa de prevenção total", () => {
  const rx = /(100\s*%|totalmente|integralmente|completamente|todos os erros)\s*(d\w+\s+erros?\s*)?(preven|evit|elimin)\w*|(preven|evit|elimin)\w+\s+(100\s*%|totalmente|integralmente|todos os erros)/i;
  for (const f of indexaveis) {
    for (const { alvo: j, contexto: ctx } of janelas(corpo(ler(f)))) {
      if (rx.test(j) && !NEGA.test(ctx)) {
        assert.fail(`${f}: promessa de prevenção total — "${j.slice(0, 150)}"`);
      }
    }
  }
});

// ── Y/Z — estimativa de 2024 x norma vigente (ROUND BLOG 30/08-K) ───────────
test("Y: percentuais de 2024 nunca aparecem como alíquota fixada ou vigente", () => {
  // Forma da tese proibida, não frase literal: um dos percentuais ligado a
  // qualquer predicado de definitividade/vigência.
  //
  // A isenção NÃO pode ser a mera presença da palavra "estimativa": ela
  // aparece dentro da própria tese proibida ("a estimativa de 2024 passa a
  // valer como norma"). Só nega a tese uma negação explícita.
  //
  // Linhas de citação (`>`) ficam fora: ali o artigo reproduz a formulação
  // alheia para repudiá-la, e a prosa ao redor é que se pronuncia.
  const pct = /\b(8,8|17,7|26,5)\s?%/;
  const definitiv = /definitiv\w*|fixad\w*|vigente|em vigor|ser[áa]\s+(a\s+)?al[íi]quota|al[íi]quota\s+(de\s+)?refer[êe]ncia\s+(vigente|atual)|automaticamente aplic\w*|passa(m)? a valer|norma tribut\w*/i;
  const NEGA_TESE = /\bn[ãa]o\b|\bnunca\b|\bjamais\b|\bnem\b|\bsem\b|deixou de|equivocad|incorret/i;
  for (const f of indexaveis) {
    for (const { alvo: j, contexto: ctx } of janelas(corpo(ler(f)))) {
      if (/^\s*>/.test(j)) continue;
      if (pct.test(j) && definitiv.test(j)) {
        assert.match(ctx, NEGA_TESE, `${f}: percentual de 2024 como alíquota fixada/vigente — "${j.slice(0, 150)}"`);
      }
    }
  }
});

test("Z: a proveniência dos percentuais de 2024 tem fonte oficial e limpa", () => {
  for (const f of arquivos) {
    const s = ler(f);
    const blocos = (/^provenance:\n([\s\S]*?)(?=^\w|\n---)/m.exec(s)?.[1] ?? "").split(/\n  - /).filter(Boolean);
    for (const b of blocos) {
      const url = /source_url:\s*"([^"]*)"/.exec(b)?.[1] ?? "";
      assert.notEqual(url.trim(), "", `${f}: claim sem source_url`);
      assert.ok(!/^PENDENTE$/i.test(url), `${f}: source_url ainda marcado como pendente`);
      // Tracking nunca entra na proveniência: a URL é o endereço do artefato,
      // não um link de campanha. Um utm_ carrega origem de navegação para
      // dentro do registro de fonte — e a origem da navegação não é a fonte.
      assert.ok(
        !/[?&](utm_[a-z]+|gclid|fbclid|si)=/i.test(url),
        `${f}: source_url com parâmetro de rastreamento — "${url}"`,
      );
      // O claim da estimativa de 2024 se ancora no Ministério da Fazenda.
      if (/\b(8,8|17,7|26,5)\b/.test(b)) {
        assert.match(
          url,
          /^https:\/\/www\.gov\.br\/fazenda\//,
          `${f}: estimativa de 2024 fora do domínio oficial da Fazenda — "${url}"`,
        );
      }
    }
  }
});

// ── Q — Invalid Date (não regredir) ─────────────────────────────────────────
test("Q: nenhuma data do blog volta ao padrão defeituoso", () => {
  for (const arq of ["app/blog/page.tsx", "app/blog/[slug]/page.tsx", "app/blog/feed.xml/route.ts"]) {
    assert.ok(!readFileSync(join(raiz, "src", arq), "utf8").includes('+ "T00:00:00"'), arq);
  }
});
