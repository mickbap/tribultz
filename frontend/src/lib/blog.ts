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
};

export type Post = PostFrontmatter & {
  content: string;
  readingTime: number;
};

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
