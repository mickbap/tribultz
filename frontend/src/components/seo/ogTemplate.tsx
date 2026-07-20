/**
 * Template compartilhado das imagens Open Graph (1200×630) geradas via
 * ImageResponse/Satori. Usado por `app/opengraph-image.tsx` (site) e
 * `app/blog/[slug]/opengraph-image.tsx` (por post).
 *
 * Satori só suporta flexbox — todo container com múltiplos filhos precisa
 * de display:flex explícito.
 */

export const OG_SIZE = { width: 1200, height: 630 };

/** Marca Tribultz (mesma geometria do TribultzLogo em PublicNavbar). */
export function TribultzMark({ size = 72 }: { size?: number }) {
  return (
    <svg viewBox="0 0 40 40" width={size} height={size}>
      <rect x="2" y="2" width="36" height="36" rx="9" fill="#2956E3" />
      <path d="M11 14 H29 M20 14 V32" stroke="#FFFFFF" strokeWidth="4" strokeLinecap="round" />
      <circle cx="29" cy="32" r="2.5" fill="#FFD600" />
    </svg>
  );
}

export function OgTemplate({
  badge,
  title,
  subtitle,
}: {
  badge: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "64px 72px",
        background: "linear-gradient(135deg, #2956E3 0%, #1a328b 100%)",
        color: "#FFFFFF",
        fontFamily: "sans-serif",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <TribultzMark size={64} />
        <span style={{ fontSize: 40, fontWeight: 800, letterSpacing: -1 }}>Tribultz</span>
        <span
          style={{
            marginLeft: 16,
            padding: "6px 18px",
            borderRadius: 999,
            background: "rgba(255,255,255,0.14)",
            border: "1px solid rgba(255,255,255,0.25)",
            fontSize: 24,
            fontWeight: 600,
          }}
        >
          {badge}
        </span>
      </div>

      <div
        style={{
          display: "flex",
          fontSize: title.length > 70 ? 52 : 62,
          fontWeight: 800,
          lineHeight: 1.15,
          letterSpacing: -1,
          maxWidth: 1020,
        }}
      >
        {title}
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 28, color: "rgba(255,255,255,0.82)" }}>{subtitle}</span>
        <span style={{ fontSize: 28, fontWeight: 700, color: "#FFD600" }}>tribultz.com.br</span>
      </div>
    </div>
  );
}
