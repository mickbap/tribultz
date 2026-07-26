import { ImageResponse } from "next/og";
import { TribultzMark } from "@/components/seo/ogTemplate";

/**
 * Favicon gerado a partir da mesma geometria SVG do TribultzLogo (mesmo
 * padrão de logo.png/route.tsx) — o favicon.ico anterior era um placeholder
 * genérico (círculo preto + triângulo) que não correspondia à marca real.
 */
export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div style={{ display: "flex", width: "100%", height: "100%" }}>
        <TribultzMark size={32} />
      </div>
    ),
    { ...size },
  );
}
