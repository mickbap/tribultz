import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/dashboard",
          "/validate-xml",
          "/validate-batch",
          "/jobs",
          "/audit",
          "/billing",
          "/settings",
          "/support",
          "/admin",
          "/closing",
          "/exceptions",
          "/documents",
          "/feedback",
          "/report",
          "/select-mode",
          "/cerebro",
        ],
      },
    ],
    sitemap: "https://tribultz.com.br/sitemap.xml",
  };
}
