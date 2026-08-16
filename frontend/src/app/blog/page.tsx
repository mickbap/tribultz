import type { Metadata } from "next";
import Link from "next/link";
import { getAllPosts } from "@/lib/blog";
import { JsonLd } from "@/components/seo/JsonLd";
import { formatPostDate } from "@/lib/formatPostDate";

const SITE_URL = "https://tribultz.com.br";

export const metadata: Metadata = {
  title: "Blog — Reforma Tributária CBS/IBS",
  description:
    "Artigos técnicos sobre cClassTrib, NCM, Rejeição 1024 e compliance CBS/IBS para a Reforma Tributária de 2026.",
  alternates: { canonical: `${SITE_URL}/blog` },
};

export default function BlogListPage() {
  const posts = getAllPosts();

  return (
    <>
      <JsonLd
        data={{
          "@type": "Blog",
          "@id": `${SITE_URL}/blog#blog`,
          "name": "Tribultz Blog",
          "url": `${SITE_URL}/blog`,
          "description": "Artigos técnicos sobre a Reforma Tributária CBS/IBS.",
          "publisher": {
            "@type": "Organization",
            "name": "Tribultz",
            "@id": `${SITE_URL}/#org`,
          },
          "inLanguage": "pt-BR",
        }}
      />
      <main className="mx-auto max-w-3xl px-4 py-16">
        <header className="mb-12">
          <nav className="mb-4 text-sm text-slate-500">
            <Link href="/" className="hover:text-slate-800">Início</Link>
            <span className="mx-2">/</span>
            <span className="text-slate-800">Blog</span>
          </nav>
          <h1 className="text-4xl font-bold text-slate-900">Blog</h1>
          <p className="mt-3 text-lg text-slate-600">
            Artigos técnicos sobre cClassTrib, NCM, CBS/IBS e a Reforma Tributária de 2026.
          </p>
        </header>

        {posts.length === 0 ? (
          <p className="text-slate-500">Nenhum post publicado ainda.</p>
        ) : (
          <ul className="space-y-8">
            {posts.map((post) => (
              <li key={post.slug} className="border-b border-slate-100 pb-8">
                <article>
                  <span className="text-xs font-semibold uppercase tracking-wide text-blue-600">
                    {post.category}
                  </span>
                  <h2 className="mt-1 text-2xl font-bold text-slate-900 hover:text-blue-700">
                    <Link href={`/blog/${post.slug}`}>{post.title}</Link>
                  </h2>
                  <p className="mt-2 text-slate-600">{post.description}</p>
                  <div className="mt-3 flex items-center gap-4 text-sm text-slate-500">
                    <time dateTime={post.publishedAt}>
                      {formatPostDate(post.publishedAt)}
                    </time>
                    <span>·</span>
                    <span>{post.author.name}</span>
                  </div>
                  {post.tags.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
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
                  <Link
                    href={`/blog/${post.slug}`}
                    className="mt-4 inline-block text-sm font-semibold text-blue-700 hover:underline"
                  >
                    Ler artigo →
                  </Link>
                </article>
              </li>
            ))}
          </ul>
        )}
      </main>
    </>
  );
}
