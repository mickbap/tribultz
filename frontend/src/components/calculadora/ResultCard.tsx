"use client";

type TaxBreakdown = {
  label: string;
  value: number;
  rate: number;
};

export type CalculadoraResult = {
  vBC: number;
  cbs: TaxBreakdown;
  ibsUf: TaxBreakdown;
  ibsMun: TaxBreakdown;
  total: number;
  effectiveRate: number;
};

type ResultCardProps = {
  result: CalculadoraResult;
};

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function formatPct(value: number): string {
  return `${value.toFixed(2)}%`;
}

function Row({
  label,
  value,
  rate,
  colorClass,
}: {
  label: string;
  value: number;
  rate: number;
  colorClass: string;
}) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-2.5 last:border-b-0">
      <div className="flex items-center gap-2">
        <span className={`inline-block h-2.5 w-2.5 rounded-full ${colorClass}`} />
        <span className="text-sm text-slate-600">{label}</span>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-xs text-slate-400">{formatPct(rate)}</span>
        <span className="text-sm font-medium text-slate-800">{formatBRL(value)}</span>
      </div>
    </div>
  );
}

export function ResultCard({ result }: ResultCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      {/* Header: Base de calculo */}
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-slate-500">Base de Calculo (vBC)</span>
          <span className="text-base font-semibold text-slate-800">
            {formatBRL(result.vBC)}
          </span>
        </div>
      </div>

      {/* Tax breakdown */}
      <div className="px-5 py-3">
        <Row
          label={result.cbs.label}
          value={result.cbs.value}
          rate={result.cbs.rate}
          colorClass="bg-blue-500"
        />
        <Row
          label={result.ibsUf.label}
          value={result.ibsUf.value}
          rate={result.ibsUf.rate}
          colorClass="bg-emerald-500"
        />
        <Row
          label={result.ibsMun.label}
          value={result.ibsMun.value}
          rate={result.ibsMun.rate}
          colorClass="bg-emerald-400"
        />
      </div>

      {/* Total */}
      <div className="rounded-b-xl border-t border-slate-200 bg-slate-50 px-5 py-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-semibold text-slate-700">Total CBS + IBS</span>
            <span className="ml-3 text-xs text-slate-400">
              Aliquota efetiva: {formatPct(result.effectiveRate)}
            </span>
          </div>
          <span className="text-lg font-bold text-slate-900">{formatBRL(result.total)}</span>
        </div>
      </div>
    </div>
  );
}
