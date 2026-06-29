import type { NextConfig } from "next";

// Use || so empty-string env var (common misconfiguration) also falls back.
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-XSS-Protection", value: "1; mode=block" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://challenges.cloudflare.com https://*.googletagmanager.com https://js.hs-scripts.com https://*.hs-scripts.com https://js.hs-analytics.net https://js.hs-banner.com https://js.hsadspixel.net https://js.usemessages.com https://*.hsforms.net",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https://*.google-analytics.com https://*.googletagmanager.com https://*.hubspot.com https://*.hs-analytics.net",
      "font-src 'self'",
      `connect-src 'self' ${apiBase} https://challenges.cloudflare.com https://*.google-analytics.com https://*.analytics.google.com https://*.googletagmanager.com https://*.hubspot.com https://*.hubapi.com https://*.hs-analytics.net`,
      "frame-src https://challenges.cloudflare.com https://*.hubspot.com",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
