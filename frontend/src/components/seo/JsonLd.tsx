/**
 * JsonLd — server-rendered schema.org JSON-LD snippet.
 *
 * Usage:
 *   <JsonLd data={{ "@context": "https://schema.org", "@type": "FAQPage", ... }} />
 *
 * Accepts either a single schema object or a @graph array. Always renders as
 * <script type="application/ld+json"> inside the page's React tree.
 *
 * Server component — no client JS shipped.
 */

type SchemaValue =
  | string
  | number
  | boolean
  | null
  | SchemaValue[]
  | { [key: string]: SchemaValue };

export type SchemaObject = Record<string, SchemaValue>;

export function JsonLd({ data }: { data: SchemaObject | SchemaObject[] }) {
  // Stable, compact, no extra whitespace. Browsers don't care about pretty-print.
  const payload = Array.isArray(data)
    ? { "@context": "https://schema.org", "@graph": data }
    : data;
  return (
    <script
      type="application/ld+json"
      // eslint-disable-next-line react/no-danger
      dangerouslySetInnerHTML={{ __html: JSON.stringify(payload) }}
    />
  );
}
