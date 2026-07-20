import { ImageResponse } from "next/og";
import { getPostBySlug } from "@/lib/blog";
import { OgTemplate, OG_SIZE } from "@/components/seo/ogTemplate";

export const alt = "Artigo do blog Tribultz sobre a Reforma Tributária";
export const size = OG_SIZE;
export const contentType = "image/png";

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = getPostBySlug(slug);

  return new ImageResponse(
    (
      <OgTemplate
        badge={post?.category ?? "Blog"}
        title={post?.title ?? "Blog Tribultz — Reforma Tributária na prática"}
        subtitle="Blog Tribultz · Reforma Tributária"
      />
    ),
    size,
  );
}
