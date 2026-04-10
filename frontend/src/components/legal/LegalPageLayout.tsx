import Link from "next/link";
import { PublicFooter } from "@/components/public/PublicFooter";
import { PublicNavbar } from "@/components/public/PublicNavbar";
import { LEGAL_LINKS } from "@/lib/legal";

type LegalPageLayoutProps = {
  title: string;
  updatedAt: string;
  summary: string;
  children: React.ReactNode;
};

export function LegalPageLayout({
  title,
  updatedAt,
  summary,
  children,
}: LegalPageLayoutProps) {
  return (
    <>
      <PublicNavbar />
      <main className="bg-slate-50">
        <section className="border-b border-slate-200 bg-white">
          <div className="mx-auto max-w-4xl px-6 py-14">
            <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-tribultz-700">
              Central de Políticas
            </span>
            <h1 className="mt-4 text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
              {title}
            </h1>
            <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
              {summary}
            </p>
            <p className="mt-3 text-sm text-slate-500">
              Última atualização: {updatedAt}
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-4xl px-6 py-10">
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
            <div className="mb-8 flex flex-wrap gap-3">
              {LEGAL_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-700 transition hover:border-tribultz-300 hover:text-tribultz-700"
                >
                  {link.label}
                </Link>
              ))}
            </div>
            <div className="space-y-6 text-sm leading-7 text-slate-700">
              {children}
            </div>
          </div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
