type RegimeData = {
  base_old?: string | null;
  base_new?: string | null;
  icms?: string | null;
  pis?: string | null;
  cofins?: string | null;
  cbs?: string | null;
  ibs?: string | null;
  total_old?: string | null;
  total_new?: string | null;
  delta?: string | null;
};

function fmt(v: string | null | undefined): string {
  if (!v) return "—";
  const n = parseFloat(v);
  return isNaN(n) ? v : `R$ ${n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function Row({ label, old: oldVal, next }: { label: string; old: string | null | undefined; next: string | null | undefined }) {
  return (
    <tr className="border-t border-slate-100">
      <td className="py-2 pr-4 text-sm text-slate-600">{label}</td>
      <td className="py-2 pr-4 text-right font-mono text-sm text-slate-700">{fmt(oldVal)}</td>
      <td className="py-2 text-right font-mono text-sm text-slate-700">{fmt(next)}</td>
    </tr>
  );
}

export function RegimeComparison({ data }: { data: RegimeData }) {
  const delta = data.delta ? parseFloat(data.delta) : null;
  const deltaPositive = delta !== null && delta > 0;
  const deltaNegative = delta !== null && delta < 0;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="mb-1 text-sm font-semibold text-slate-700">Comparativo de Regimes</h2>
      <p className="mb-4 text-xs text-slate-500">
        Regime atual (ICMS/PIS/COFINS) × Reforma tributária (CBS/IBS) — dupla operação até 2033
      </p>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="pb-2 pr-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Campo</th>
              <th className="pb-2 pr-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Regime Atual</th>
              <th className="pb-2 text-right text-xs font-semibold uppercase tracking-wide text-tribultz-600">Reforma (CBS/IBS)</th>
            </tr>
          </thead>
          <tbody>
            {(data.base_old || data.base_new) && (
              <Row label="Base de cálculo" old={data.base_old} next={data.base_new} />
            )}
            <Row label="ICMS" old={data.icms} next={null} />
            <Row label="PIS" old={data.pis} next={null} />
            <Row label="COFINS" old={data.cofins} next={null} />
            <Row label="CBS" old={null} next={data.cbs} />
            <Row label="IBS" old={null} next={data.ibs} />
            <tr className="border-t-2 border-slate-200">
              <td className="py-2 pr-4 text-sm font-semibold text-slate-800">Total tributado</td>
              <td className="py-2 pr-4 text-right font-mono text-sm font-semibold text-slate-800">{fmt(data.total_old)}</td>
              <td className="py-2 text-right font-mono text-sm font-semibold text-tribultz-700">{fmt(data.total_new)}</td>
            </tr>
            {delta !== null && (
              <tr className="border-t border-slate-100">
                <td className="py-2 pr-4 text-sm text-slate-600">Delta (impacto)</td>
                <td className="py-2 pr-4" />
                <td className={`py-2 text-right font-mono text-sm font-semibold ${deltaPositive ? "text-red-600" : deltaNegative ? "text-emerald-600" : "text-slate-600"}`}>
                  {deltaPositive ? "+" : ""}{fmt(data.delta)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[11px] text-slate-400">
        Extraído do XML da NF. Valores negativos (verde) indicam redução de carga; positivos (vermelho) indicam aumento.
      </p>
    </section>
  );
}
