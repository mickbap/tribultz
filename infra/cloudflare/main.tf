# ══════════════════════════════════════════════════════════════════════════════
# Tribultz — Cloudflare DNS + SSL + Cache (Free Tier)
# Domínio: tribultz.com.br
#
# Proteções ativas neste plano:
#   ✅ DNS proxiado (CDN + IP masking)
#   ✅ DDoS automático (L3/L4/L7 — sempre gratuito)
#   ✅ SSL Full Strict + HSTS + TLS 1.2+
#   ✅ HTTP/2 + HTTP/3 + Brotli
#   ✅ Cache bypass para /health* e /api/*
#
# Proteções que requerem Pro ($20/mês) — removidas:
#   ❌ WAF Managed Ruleset (OWASP + CF rules)
#   ❌ WAF Custom Rules (bot block, no-UA, geo-challenge)
#   ❌ Rate Limiting via edge ruleset
#   → Cobertos no app: FastAPI rate limiter + SQLAlchemy queries parametrizadas
#
# Aplicar:
#   cd infra/cloudflare
#   cp terraform.tfvars.example terraform.tfvars  # preencher valores reais
#   terraform init
#   terraform plan
#   terraform apply
#
# Para habilitar Pro no futuro: ver infra/cloudflare/PRO_UPGRADE.md
# ══════════════════════════════════════════════════════════════════════════════

terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
  required_version = ">= 1.5"
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# ── DNS Records ───────────────────────────────────────────────────────────────

# api.tribultz.com.br → IP da VM Magalu Cloud
# proxied=true: ativa CDN, DDoS automático e mascara o IP de origem
resource "cloudflare_record" "api_a" {
  zone_id = var.zone_id
  name    = "api"
  value   = var.api_origin_ip
  type    = "A"
  proxied = true
  ttl     = 1  # Auto (gerenciado pela Cloudflare quando proxied=true)
  comment = "Tribultz API — Magalu Cloud VM"
}

# www.tribultz.com.br → Vercel
resource "cloudflare_record" "www_cname" {
  zone_id = var.zone_id
  name    = "www"
  value   = "cname.vercel-dns.com"
  type    = "CNAME"
  proxied = true
  ttl     = 1
  comment = "Frontend Vercel"
}

# ── SSL/TLS + Segurança ───────────────────────────────────────────────────────

resource "cloudflare_zone_settings_override" "tribultz" {
  zone_id = var.zone_id

  settings {
    # Full (Strict) — Cloudflare valida o cert do origin
    ssl = "strict"

    # Força HTTPS para todo o tráfego
    always_use_https = "on"

    # HSTS 6 meses, incluindo subdomínios
    security_header {
      enabled            = true
      include_subdomains = true
      max_age            = 15768000
      nosniff            = true
      preload            = true
    }

    # TLS 1.2 mínimo
    min_tls_version = "1.2"

    # TLS 1.3 com 0-RTT
    tls_1_3 = "zrt"

    # Nível de segurança padrão (sem WAF, usa heurísticas básicas CF)
    security_level = "medium"

    # Browser cache: 4 horas
    browser_cache_ttl = 14400

    # Brotli compression
    brotli = "on"

    # HTTP/2 e HTTP/3
    http2 = "on"
    http3 = "on"

    # Ocultar informações do servidor
    server_side_exclude = "on"

    # Email obfuscation
    email_obfuscation = "on"
  }
}

# ── Page Rules — Cache bypass ─────────────────────────────────────────────────
# Free tier: até 3 page rules. Usamos 2.

# Health check: sempre fresco (não cachear status de infra)
resource "cloudflare_page_rule" "no_cache_health" {
  zone_id  = var.zone_id
  target   = "api.tribultz.com.br/health*"
  priority = 1

  actions {
    cache_level = "bypass"
  }
}

# API: sem cache (dados fiscais em tempo real)
resource "cloudflare_page_rule" "no_cache_api" {
  zone_id  = var.zone_id
  target   = "api.tribultz.com.br/api/*"
  priority = 2

  actions {
    cache_level = "bypass"
  }
}
