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
test("A: 960 não volta a ser associada a cClassTrib", () => {
  const s = um("rejeicao-960-nf-e");
  const texto = corpo(s);
  // Só a negativa explícita é permitida ("não é uma rejeição de cClassTrib").
  for (const m of texto.matchAll(/[^.]*cClassTrib[^.]*\./g)) {
    assert.match(m[0], /\bnão\b/i, `960 afirma algo sobre cClassTrib: "${m[0].trim()}"`);
  }
});

test("B: 960 usa v1.60 como versão corrente, nunca v1.51 da NT 2023.001", () => {
  const s = um("rejeicao-960-nf-e");
  assert.match(s, /artifact:\s*"NT 2023\.001"[\s\S]{0,200}?artifact_version:\s*"1\.60"/);
  assert.ok(
    !/NT 2023\.001[^\n]{0,40}v?1\.51/.test(s),
    "v1.51 é histórica da NT 2023.001 — não pode voltar como corrente",
  );
});

test("C: 960 registra a exceção corrente finNFe=5/6", () => {
  const s = um("rejeicao-960-nf-e");
  assert.match(corpo(s), /finNFe=5/, "corpo precisa registrar a exceção NF-e de Crédito");
  assert.match(corpo(s), /finNFe=6/, "corpo precisa registrar a exceção NF-e de Débito");
  assert.match(s, /rule_item:\s*"N12-110, Excecao"/);
});

test("960: sem RTC como origem e sem 03/08/2026", () => {
  const t = corpo(um("rejeicao-960-nf-e"));
  assert.ok(!/03\/08\/2026|03\/08/.test(t), "960 não tem relação com 03/08/2026");
  for (const m of t.matchAll(/[^.]*Reforma Tribut[^.]*\./g)) {
    assert.match(m[0], /\bnão\b/i, `960 associa a RTC como origem: "${m[0].trim()}"`);
  }
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
    [/[Ss]ugest[ãa]o[^.]{0,40}(certificad|garante|determina)/i, "CFF Sugestão como classificação certificada"],
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
    assert.ok(!/RGI\s*3\s*b[^.]{0,40}(maior valor|mais específic)/i.test(t), `${f}: RGI 3b incorreta`);
    assert.ok(!/RGI\s*3\s*c[^.]{0,40}mais específic/i.test(t), `${f}: RGI 3c incorreta`);
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
        /estimativ|projeç|refer[êe]ncia|não\s+fixad|aguard/i,
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
 * Os sete P0 da auditoria de 30/08/2026. Seis foram reindexados com baseline
 * editorial aprovado; o sétimo segue contido por divergência aberta entre o
 * contrato e a NT 2025.002-RTC v1.51 quanto à produção da UB12-10.
 */
test("P0 reindexado carrega META_TITLE aprovado e proveniência por claim", () => {
  const reindexados = [
    "rejeicao-960-nf-e",
    "rejeicao-1024-nfe-cbs-ibs-como-corrigir",
    "classtrib-2026-mapear-ncm-regime-ibs-cbs",
    "classtrib-2026-ncm-mapeamento-completo",
    "como-classificar-ncm-corretamente-2026",
    "como-calcular-aliquota-cbs-ibs",
  ];
  for (const slug of reindexados) {
    const s = um(slug);
    assert.ok(indexaveis.includes(`${slug}.mdx`), `${slug}: reindexado não pode voltar a conter`);
    assert.match(s, /^provenance:$/m, `${slug}: sem bloco provenance`);
  }
  // O 960 veio do Round D/E, sem META_TITLE próprio; os seis do ADENDO têm.
  for (const slug of reindexados.slice(1)) {
    assert.match(um(slug), /^metaTitle:\s*"[^"]+"/m, `${slug}: META_TITLE aprovado ausente`);
  }
});

test("P0 contido declara a divergência que o mantém fora do índice", () => {
  const s = um("nfe-rejeitada-03-08-2026-regime-normal-crt3");
  assert.ok(contido(s), "não reindexar enquanto a divergência da UB12-10 estiver aberta");
  assert.match(s, /noindexReason:[^\n]*[Dd]ivergencia/, "a contenção precisa dizer por quê");
});

// ── Q — Invalid Date (não regredir) ─────────────────────────────────────────
test("Q: nenhuma data do blog volta ao padrão defeituoso", () => {
  for (const arq of ["app/blog/page.tsx", "app/blog/[slug]/page.tsx", "app/blog/feed.xml/route.ts"]) {
    assert.ok(!readFileSync(join(raiz, "src", arq), "utf8").includes('+ "T00:00:00"'), arq);
  }
});
