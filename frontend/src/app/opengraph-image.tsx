import { ImageResponse } from "next/og";
import { OgTemplate, OG_SIZE } from "@/components/seo/ogTemplate";

export const alt = "Tribultz — Validação CBS/IBS e compliance da Reforma Tributária (LC 214)";
export const size = OG_SIZE;
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <OgTemplate
        badge="LC 214"
        title="IBS e CBS sem erro. Sem multa. Sem susto."
        subtitle="Validação CBS/IBS · cClassTrib · Evite a Rejeição 1024"
      />
    ),
    size,
  );
}
