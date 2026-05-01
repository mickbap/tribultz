import Link from "next/link";

export function PublicNavbar() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3 md:px-6">
        <Link href="/" className="flex flex-col leading-tight shrink-0">
          <span className="text-lg font-bold tracking-wide text-tribultz-600">Tribultz</span>
          <span className="hidden text-[10px] font-medium text-slate-500 sm:block">
            IBS e CBS sem erro. Sem multa. Sem susto.
          </span>
        </Link>

        <nav className="flex items-center gap-6 text-sm" aria-label="Navegação pública">
          <Link
            href="/diagnostico"
            className="font-medium text-slate-700 hover:text-tribultz-600"
          >
            Diagnóstico Gratuito
          </Link>
          <Link
            href="/calculadora"
            className="font-medium text-slate-700 hover:text-tribultz-600"
          >
            Calculadora CBS/IBS
          </Link>
          <Link
            href="/pricing"
            className="font-medium text-slate-700 hover:text-tribultz-600"
          >
            Planos
          </Link>
          <Link
            href="/login"
            className="font-medium text-slate-500 hover:text-slate-700"
          >
            Entrar
          </Link>
        </nav>

        <Link
          href="/register"
          className="ml-auto shrink-0 rounded-lg bg-tribultz-600 px-4 py-2 text-sm font-semibold text-white hover:bg-tribultz-700"
        >
          Criar Conta
        </Link>
      </div>
    </header>
  );
}
