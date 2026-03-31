import Link from "next/link";
import { PublicFooter } from "@/components/public/PublicFooter";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { NewsFeed } from "@/components/public/NewsFeed";

export default function ChangelogPage() {
  return (
    <>
      <PublicNavbar />

      <main className="min-h-screen">
        <section className="border-b border-slate-200 bg-white/70">
          <div className="mx-auto max-w-5xl px-4 py-14 md:px-6">
            <Link href="/" className="text-sm font-medium text-tribultz-700 hover:underline">
              Voltar para a Home
            </Link>
            <h1 className="mt-4 text-4xl font-black tracking-tight text-slate-950">
              Changelog do produto
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
              Este painel carrega as últimas entradas publicadas pelo endpoint
              `GET /api/v1/news`, sem depender do JSON estatico anterior.
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-5xl px-4 py-12 md:px-6">
          <NewsFeed />
        </section>
      </main>

      <PublicFooter />
    </>
  );
}
