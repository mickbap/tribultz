type JsonViewerProps = {
  data: unknown;
  title?: string;
};

export function JsonViewer({ data, title }: JsonViewerProps) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3">
      {title ? <h3 className="mb-2 text-sm font-semibold text-slate-700">{title}</h3> : null}
      <pre className="scroll-thin max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">
        {JSON.stringify(data ?? {}, null, 2)}
      </pre>
    </section>
  );
}
