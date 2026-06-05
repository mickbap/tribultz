import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { MDXRemote } from "next-mdx-remote/rsc";
import remarkGfm from "remark-gfm";
import { getAllSlugs, getPostBySlug } from "@/lib/blog";
import { JsonLd } from "@/components/seo/JsonLd";
import { FundamentacaoLegal } from "@/components/seo/FundamentacaoLegal";
import { articleSchema, breadcrumbsSchema, personSchema } from "@/components/seo/schemas";

const SITE_URL = "https://tribultz.com.br";

const MDX_OPTIONS = {
  mdxOptions: {
    remarkPlugins: [remarkGfm],
  },
};

export async function generateStaticParams() {
  return getAllSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) return {};
  return {
    title: `${post.title} | Tribultz`,
    description: post.description,
    alternates: { canonical: `${SITE_URL}/blog/${post.slug}` },
    openGraph: {
      title: post.title,
      description: post.description,
      url: `${SITE_URL}/blog/${post.slug}`,
      type: "article",
      publishedTime: post.publishedAt,
      modifiedTime: post.updatedAt,
      authors: [post.author.name],
      ...(post.coverImage ? { images: [post.coverImage] } : {}),
    },
  };
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) notFound();

  const postUrl = `${SITE_URL}/blog/${post.slug}`;

  const schemas = [
    articleSchema({
      url: postUrl,
      title: post.title,
      description: post.description,
      publishedAt: post.publishedAt,
      updatedAt: post.updatedAt,
      author: post.author,
      coverImage: post.coverImage,
    }),
    breadcrumbsSchema([
      { name: "Início", url: SITE_URL },
      { name: "Blog", url: `${SITE_URL}/blog` },
      { name: post.title, url: postUrl },
    ]),
    personSchema({
      name: post.author.name,
      url: post.author.url,
      jobTitle: post.author.jobTitle,
      credentials: post.author.credentials,
    }),
  ];

  return (
    <>
      <JsonLd data={schemas} />
      <main className="mx-auto max-w-3xl px-4 py-16">
        <nav className="mb-8 text-sm text-slate-500">
          <Link href="/" className="hover:text-slate-800">Início</Link>
          <span className="mx-2">/</span>
          <Link href="/blog" className="hover:text-slate-800">Blog</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-800 line-clamp-1">{post.title}</span>
        </nav>

        <article>
          <header className="mb-10">
            <span className="text-xs font-semibold uppercase tracking-wide text-blue-600">
              {post.category}
            </span>
            <h1 className="mt-2 text-4xl font-bold leading-tight text-slate-900">
              {post.title}
            </h1>
            <p className="mt-4 text-xl text-slate-600">{post.description}</p>
            <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-slate-100 pt-6 text-sm text-slate-500">
              <div>
                <span className="font-medium text-slate-700">{post.author.name}</span>
                <span className="ml-1">— {post.author.jobTitle}</span>
              </div>
              <span>·</span>
              <time dateTime={post.publishedAt}>
                {new Date(post.publishedAt + "T00:00:00").toLocaleDateString("pt-BR", {
                  day: "2-digit",
                  month: "long",
                  year: "numeric",
                })}
              </time>
              <span>·</span>
              <span>{post.readingTime} min de leitura</span>
            </div>
            {post.tags.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {post.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-slate-100 px-3 py-0.5 text-xs text-slate-600"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </header>

          <div className="prose prose-slate max-w-none">
            <MDXRemote
              source={post.content}
              options={MDX_OPTIONS}
            />
          </div>

          {post.legalRefs && post.legalRefs.length > 0 && (
            <FundamentacaoLegal items={post.legalRefs} />
          )}
        </article>

        <footer className="mt-16 border-t border-slate-100 pt-8">
          <Link
            href="/blog"
            className="text-sm font-semibold text-blue-700 hover:underline"
          >
            ← Voltar para o Blog
          </Link>
        </footer>
      </main>
    </>
  );
}
