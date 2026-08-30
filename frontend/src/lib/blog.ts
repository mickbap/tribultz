import fs from "fs";
import path from "path";
import matter from "gray-matter";
import type { LegalRef } from "@/components/seo/FundamentacaoLegal";

const CONTENT_DIR = path.join(process.cwd(), "content", "blog");

export type PostAuthor = {
  name: string;
  jobTitle: string;
  credentials?: string;
  url: string;
};

export type PostFrontmatter = {
  title: string;
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
