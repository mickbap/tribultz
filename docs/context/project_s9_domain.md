---
name: S9 domain and hosting
description: Domain tribultz.com.br acquired via Hostinger, DNS pointed to Cloudflare, Turnstile widget created.
type: project
---

Domain tribultz.com.br acquired via Hostinger. DNS nameservers changed to Cloudflare (anna.ns.cloudflare.com, justin.ns.cloudflare.com) on 2026-03-22.

Cloudflare Turnstile widget "Tribultz Console" created with:
- Hostnames: tribultz.com.br + localhost
- Mode: Managed (Recommended)
- Site Key: 0x4AAAAAACukcOT9w9KF8vHm (public, safe for frontend)
- Secret Key: stored in backend .env only (NEVER commit)

**Why:** CAPTCHA required for login/register to prevent brute-force and bot abuse.

**How to apply:** Use NEXT_PUBLIC_TURNSTILE_SITE_KEY env var in frontend, TURNSTILE_SECRET_KEY in backend .env. Backend captcha_service.py already validates tokens. Frontend needs widget integration on login + register pages.
