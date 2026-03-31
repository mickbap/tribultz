# ══════════════════════════════════════════════════════════════════════════════
# Tribultz — Cloudflare WAF + Rate Limiting + DNS
# Domínio: tribultz.com.br
#
# Aplicar:
#   cd infra/cloudflare
#   cp terraform.tfvars.example terraform.tfvars  # preencher valores reais
#   terraform init
#   terraform plan
#   terraform apply
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
# Proxied = true ativa WAF, rate limiting e DDoS protection via Cloudflare
resource "cloudflare_record" "api_a" {
  zone_id = var.zone_id
  name    = "api"
  value   = var.api_origin_ip
  type    = "A"
  proxied = true
  ttl     = 1  # Auto (gerenciado pela Cloudflare quando proxied=true)
  comment = "Tribultz API — Magalu Cloud VM"
}

# www.tribultz.com.br → Vercel (CNAME para alias Vercel)
resource "cloudflare_record" "www_cname" {
  zone_id = var.zone_id
  name    = "www"
  value   = "cname.vercel-dns.com"
  type    = "CNAME"
  proxied = true
  ttl     = 1
  comment = "Frontend Vercel"
}

# ── SSL/TLS ───────────────────────────────────────────────────────────────────

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

    # Desativa versões antigas de TLS
    tls_1_3 = "zrt"

    # Modo de segurança: High
    security_level = "high"

    # Browser cache: 4 horas
    browser_cache_ttl = 14400

    # Brotli compression
    brotli = "on"

    # HTTP/2 e HTTP/3
    http2 = "on"
    http3 = "on"

    # Ocultar versão do servidor (X-Powered-By etc.)
    server_side_exclude = "on"

    # Email obfuscation
    email_obfuscation = "on"
  }
}

# ── WAF — Managed Rulesets ────────────────────────────────────────────────────

# Ativa o Cloudflare Managed Ruleset (OWASP Top 10 + Cloudflare rules)
resource "cloudflare_ruleset" "waf_managed" {
  zone_id     = var.zone_id
  name        = "Tribultz WAF Managed Rules"
  description = "OWASP + Cloudflare Managed Rules para api.tribultz.com.br"
  kind        = "zone"
  phase       = "http_request_firewall_managed"

  rules {
    action      = "execute"
    description = "Cloudflare Managed Ruleset"
    enabled     = true
    expression  = "true"

    action_parameters {
      id = "efb7b8c949ac4650a09736fc376e9aee"  # Cloudflare Managed Ruleset ID
      overrides {
        # Bloquear SQL Injection, XSS, RCE
        action  = "block"
        enabled = true
      }
    }
  }

  rules {
    action      = "execute"
    description = "Cloudflare OWASP Core Ruleset"
    enabled     = true
    expression  = "true"

    action_parameters {
      id = "4814384a9e5d4991b9815dcfc25d2f1f"  # OWASP Core Ruleset ID
      overrides {
        action  = "block"
        enabled = true
        # Sensitivity: high para API, low para frontend
        rules {
          id      = "6179ae15870a4bb7b2d480d4843b323c"
          enabled = true
          score_threshold = 40
        }
      }
    }
  }
}

# ── WAF — Custom Rules ────────────────────────────────────────────────────────

resource "cloudflare_ruleset" "waf_custom" {
  zone_id     = var.zone_id
  name        = "Tribultz Custom WAF Rules"
  description = "Regras customizadas para proteger endpoints fiscais"
  kind        = "zone"
  phase       = "http_request_firewall_custom"

  # Bloqueia bots conhecidos agressivos
  rules {
    action      = "block"
    description = "Block aggressive bots and scanners"
    enabled     = true
    expression  = <<-EOT
      (cf.client.bot) and
      not (cf.verified_bot_category in {"Search Engine Crawler" "Monitoring & Analytics"})
    EOT
  }

  # Bloqueia requests sem User-Agent (scrapers primitivos)
  rules {
    action      = "block"
    description = "Block requests without User-Agent"
    enabled     = true
    expression  = <<-EOT
      (http.request.uri.path contains "/api/v1/") and
      (not http.user_agent matches ".")
    EOT
  }

  # Protege endpoints de autenticação: só aceita POST com Content-Type JSON
  rules {
    action      = "block"
    description = "Auth endpoints must send JSON Content-Type"
    enabled     = true
    expression  = <<-EOT
      (http.request.uri.path contains "/api/v1/auth/") and
      (http.request.method eq "POST") and
      (not http.request.headers["content-type"][0] contains "application/json")
    EOT
  }

  # Challenge para países de alto risco acessando endpoints de pagamento
  rules {
    action      = "managed_challenge"
    description = "Challenge high-risk countries on billing endpoints"
    enabled     = true
    expression  = <<-EOT
      (http.request.uri.path contains "/api/v1/billing/") and
      (ip.geoip.country in {"CN" "RU" "KP" "IR" "BY" "CU"})
    EOT
  }
}

# ── Rate Limiting ─────────────────────────────────────────────────────────────

resource "cloudflare_ruleset" "rate_limiting" {
  zone_id     = var.zone_id
  name        = "Tribultz Rate Limiting Rules"
  description = "Rate limiting por endpoint — calculadora, auth, billing"
  kind        = "zone"
  phase       = "http_ratelimit"

  # /api/v1/public/calculadora — 20 req/min por IP
  rules {
    action      = "block"
    description = "Rate limit: calculadora 20 req/60s por IP"
    enabled     = true
    expression  = "(http.request.uri.path contains \"/api/v1/public/calculadora\")"

    ratelimit {
      characteristics     = ["ip.src"]
      period              = 60
      requests_per_period = 20
      mitigation_timeout  = 60
    }
  }

  # /api/v1/auth/login — 5 tentativas/min (anti brute-force)
  rules {
    action      = "block"
    description = "Rate limit: login 5 req/60s por IP"
    enabled     = true
    expression  = "(http.request.uri.path eq \"/api/v1/auth/login\")"

    ratelimit {
      characteristics     = ["ip.src"]
      period              = 60
      requests_per_period = 5
      mitigation_timeout  = 300  # bloqueia por 5 min após exceder
    }
  }

  # /api/v1/auth/register — 3 contas/min por IP (anti spam)
  rules {
    action      = "block"
    description = "Rate limit: register 3 req/60s por IP"
    enabled     = true
    expression  = "(http.request.uri.path eq \"/api/v1/auth/register\")"

    ratelimit {
      characteristics     = ["ip.src"]
      period              = 60
      requests_per_period = 3
      mitigation_timeout  = 300
    }
  }

  # /api/v1/auth/forgot-password — 3 req/min (anti enumeration)
  rules {
    action      = "block"
    description = "Rate limit: forgot-password 3 req/60s por IP"
    enabled     = true
    expression  = "(http.request.uri.path eq \"/api/v1/auth/forgot-password\")"

    ratelimit {
      characteristics     = ["ip.src"]
      period              = 60
      requests_per_period = 3
      mitigation_timeout  = 300
    }
  }

  # /api/v1/billing/webhook — 50 req/min (Asaas webhooks legítimos)
  rules {
    action      = "block"
    description = "Rate limit: billing webhook 50 req/60s"
    enabled     = true
    expression  = "(http.request.uri.path contains \"/api/v1/billing/webhook\")"

    ratelimit {
      characteristics     = ["ip.src"]
      period              = 60
      requests_per_period = 50
      mitigation_timeout  = 60
    }
  }

  # API global — 200 req/min por IP (proteção genérica)
  rules {
    action      = "block"
    description = "Rate limit: API global 200 req/60s por IP"
    enabled     = true
    expression  = "(http.request.uri.path starts_with \"/api/\")"

    ratelimit {
      characteristics     = ["ip.src"]
      period              = 60
      requests_per_period = 200
      mitigation_timeout  = 60
    }
  }
}

# ── Page Rules — Cache ────────────────────────────────────────────────────────

# Health check: sem cache (sempre fresco)
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
