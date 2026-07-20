import { ImageResponse } from "next/og";
import { TribultzMark } from "@/components/seo/ogTemplate";

/**
 * Serve a marca oficial em /logo.png (512×512) — URL referenciada pelo
 * JSON-LD Organization da home. Gerada em build (force-static) a partir da
 * mesma geometria SVG do TribultzLogo, sem asset binário no repositório.
 */
export const dynamic = "force-static";

export function GET() {
  return new ImageResponse(
    (
      <div style={{ display: "flex", width: "100%", height: "100%" }}>
        <TribultzMark size={512} />
      </div>
    ),
    { width: 512, height: 512 },
  );
}
