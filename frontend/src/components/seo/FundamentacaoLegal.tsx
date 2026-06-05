/**
 * Tabela de fundamentação legal — server component, semantic HTML.
 *
 * Reusable em posts de blog e páginas-ferramenta. Renderiza <table> com
 * cabeçalho fixo + linhas. O conteúdo da tabela é um sinal forte de
 * autoridade no Google (formato canônico de referência).
 *
 * Cada linha aceita link opcional para o instrumento oficial.
 */

export type LegalRef = {
  instrumento: string;
  artigo?: string;
  descricao: string;
  link?: string;
};

export function FundamentacaoLegal({ items, title = "Fundamentação legal" }: {
  items: LegalRef[];
  title?: string;
}) {
  return (
    <section className="border-t border-slate-200 bg-white py-12">
      <div className="mx-auto max-w-3xl px-4">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">{title}</h2>
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-slate-700">Instrumento</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-700">Artigo</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-700">Aplicação</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="px-4 py-3 align-top font-mono text-xs font-semibold text-slate-800">
                    {item.link ? (
                      <a href={item.link} target="_blank" rel="noopener noreferrer nofollow" className="text-blue-700 hover:underline">
                        {item.instrumento}
                      </a>
                    ) : (
                      item.instrumento
                    )}
                  </td>
                  <td className="px-4 py-3 align-top font-mono text-xs text-slate-600">{item.artigo ?? "—"}</td>
                  <td className="px-4 py-3 align-top text-slate-700">{item.descricao}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
