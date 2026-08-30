import fs from "fs";
import path from "path";
import matter from "gray-matter";
import type { LegalRef } from "@/components/seo/FundamentacaoLegal";

/**
 * Como o produto classifica a natureza de uma afirmação técnica.
 *
 * A distinção não é estilística: `NAO_DETERMINADO` nunca pode ser renderizado
 * como afirmação factual, e `INTERPRETACAO_SEGURA` não pode ser apresentada
 * como se fosse texto de norma.
 */
export type ClaimClassification =
  | "FATO_NORMATIVO"
  | "INTERPRETACAO_SEGURA"
  | "NAO_DETERMINADO";

/**
 * Proveniência de UM claim material — não do artigo.
 *
 * Uma lista genérica de fontes no rodapé não rastreia nada: não diz qual
 * afirmação veio de onde, nem em que versão, nem quando foi conferida. Foi
 * assim que sete artigos P0 chegaram ao ar afirmando o que a norma não diz.
 *
 * `claim_scope` delimita a que a proveniência se aplica. Pode cobrir um claim
 * único ou um grupo EXPLICITAMENTE delimitado — nunca "o artigo inteiro".
 */
export type ClaimProvenance = {
  /** A que afirmação (ou grupo delimitado) esta proveniência se aplica. */
  claim_scope: string;
  claim_classification: ClaimClassification;
  /** Documento de origem: "NT 2025.002-RTC", "LC 214/2025", "IN RFB 2.057/2021". */
  artifact: string;
  /** Quem publica. Fonte secundária nunca é autoridade — só localiza. */
  source_authority: string;
  source_url: string;
  /** Data em que NÓS conferimos a afirmação contra o artefato. */
  verified_at: string;
  /** Versão do artefato, quando ele for versionado. */
  artifact_version?: string;
  /** Regra ou dispositivo de onde o claim decorre: "UB14-20", "Art. 26, §1º, II". */
  rule_item?: string;
  /** Recorte temporal, quando a dimensão temporal for material. */
  temporal_applicability?: string;
  /** Registro de conflito oficial × oficial, preservado sem conciliação. */
  conflict_note?: string;
  /**
   * Proveniência temporal/versionamento: linhagem de versões de um artefato
   * quando a versão corrente supera uma anterior.
   *
   * Distinta de `conflict_note`: conflito é divergência não conciliada entre
   * fontes; versionamento é sucessão resolvida — a versão nova prevalece, e a
   * anterior é preservada como linhagem histórica, não como estado vigente.
   */
  versioning_note?: string;
  /**
   * Limite explícito do alcance do claim: até onde ele vale e onde deixa de
   * valer. Distinto de `claim_scope`, que diz sobre o que o claim é.
   */
  claim_scope_limit?: string;
  /**
   * Claim cuja fonte oficial não pôde ser resolvida. O claim NÃO é apagado —
   * apagar esconderia a afirmação em vez de sustentá-la —, mas o artigo que o
   * contém não pode ser indexado enquanto a URL oficial não for fechada.
   *
   * Nunca preencher `source_url` com blog, agregador ou fonte secundária para
   * destravar: fonte secundária localiza, não autoriza.
   */
  provenance_blocked?: boolean;
  /** Por que a proveniência está bloqueada e o que falta para destravá-la. */
  blocked_reason?: string;
};

const CONTENT_DIR = path.join(process.cwd(), "content", "blog");

export type PostAuthor = {
  name: string;
  jobTitle: string;
  credentials?: string;
  url: string;
};

export type PostFrontmatter = {
  title: string;
  /**
   * Título de SEO aprovado pelo Jurídico quando difere do título editorial.
   * Alimenta só a tag `<title>`; o H1 e o Open Graph seguem `title`.
   * Ausente, o `<title>` cai em `title` — comportamento anterior.
   */
  metaTitle?: string;
  description: string;
  slug: string;
  category: string;
  author: PostAuthor;
  publishedAt: string;
  updatedAt?: string;
  /** Referência curta do que mudou na atualização (ex.: "NT 2025.002-RTC v1.36 → v1.40"). Exibida no rodapé junto com updatedAt. */
  updateNote?: string;
  tags: string[];
  coverImage?: string;
  legalRefs?: LegalRef[];
  /**
   * Contenção editorial REVERSÍVEL (#round-blog-30-08-A).
   *
   * `true` retira o post da listagem `/blog`, do `sitemap.xml` e do RSS, e
   * marca a página com `robots: noindex, nofollow`. A URL continua
   * respondendo e o arquivo continua versionado — contenção não é remoção:
   * apagar destruiria histórico e criaria 404 sem destino avaliado.
   *
   * Usar quando o conteúdo é tecnicamente incorreto e não pode seguir sendo
   * apresentado como orientação válida enquanto aguarda reescrita.
   */
  noindex?: boolean;
  /** Por que o post está contido. Obrigatório quando `noindex` é `true`. */
  noindexReason?: string;
  /**
   * Proveniência POR CLAIM. Obrigatória em artigo técnico indexável — ver
   * `blogProvenanceLint`. Complementa `legalRefs`, que é bibliografia de
   * rodapé e não rastreia afirmação individual.
   */
  provenance?: ClaimProvenance[];
  /**
   * Marca o artigo como técnico para o gate de proveniência. Inferido por
   * heurística quando ausente; declarar explicitamente vence a heurística.
   */
  technical?: boolean;
};

export type Post = PostFrontmatter & {
  content: string;
  readingTime: number;
};

/**
 * TODOS os posts, contidos inclusive. Use apenas onde a contenção não se
 * aplica (ex.: gerar rotas estáticas, para a URL continuar respondendo).
 */
export function getAllPosts(): PostFrontmatter[] {
  if (!fs.existsSync(CONTENT_DIR)) return [];
  return fs
    .readdirSync(CONTENT_DIR)
    .filter((f) => f.endsWith(".mdx"))
    .map((filename) => {
      const raw = fs.readFileSync(path.join(CONTENT_DIR, filename), "utf-8");
      return matter(raw).data as PostFrontmatter;
    })
    .sort(
      (a, b) =>
        new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime(),
    );
}

/**
 * Posts que podem ser indexados e listados. É esta a função que listagem,
 * sitemap e RSS devem consumir — nunca `getAllPosts`.
 */
export function getIndexablePosts(): PostFrontmatter[] {
  return getAllPosts().filter((p) => p.noindex !== true);
}

/** Slugs de TODOS os posts — a rota do post contido continua existindo. */
export function getAllSlugs(): string[] {
  return getAllPosts().map((p) => p.slug);
}

export function getPostBySlug(slug: string): Post | null {
  if (!fs.existsSync(CONTENT_DIR)) return null;
  for (const filename of fs.readdirSync(CONTENT_DIR).filter((f) => f.endsWith(".mdx"))) {
    const raw = fs.readFileSync(path.join(CONTENT_DIR, filename), "utf-8");
    const { data, content } = matter(raw);
    const fm = data as PostFrontmatter;
    if (fm.slug === slug) {
      const words = content.trim().split(/\s+/).length;
      return { ...fm, content, readingTime: Math.ceil(words / 200) };
    }
  }
  return null;
}
