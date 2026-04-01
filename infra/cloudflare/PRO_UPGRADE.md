# Cloudflare Pro Upgrade — Checklist

Quando o projeto atingir tráfego real em produção, habilitar o plano Pro ($20/mês)
desbloqueia as proteções abaixo. Os recursos já estão documentados aqui — basta
descomentar/reintegrar no `main.tf`.

## O que o Pro adiciona

| Proteção | Phase | Benefício |
|----------|-------|-----------|
| WAF Managed Ruleset (OWASP + CF rules) | `http_request_firewall_managed` | Bloqueia SQLi, XSS, RCE automaticamente |
| WAF Custom Rules | `http_request_firewall_custom` | Bloqueia bots agressivos, no-UA, geo-challenge billing |
| Rate Limiting via edge | `http_ratelimit` | calculadora:20/min, login:5/min, register:3/min, global:200/min |

## Regras prontas para reintegrar

### WAF Managed (adicionar em main.tf)

```hcl
resource "cloudflare_ruleset" "waf_managed" {
  zone_id     = var.zone_id
  name        = "Tribultz WAF Managed Rules"
  description = "OWASP + Cloudflare Managed Rules"
  kind        = "zone"
  phase       = "http_request_firewall_managed"

  rules {
    action     = "execute"
    enabled    = true
    expression = "true"
    action_parameters {
      id = "efb7b8c949ac4650a09736fc376e9aee"
      overrides { action = "block"; enabled = true }
    }
  }

  rules {
    action     = "execute"
    enabled    = true
    expression = "true"
    action_parameters {
      id = "4814384a9e5d4991b9815dcfc25d2f1f"
      overrides {
        action = "block"; enabled = true
        rules {
          id = "6179ae15870a4bb7b2d480d4843b323c"
          enabled = true
          score_threshold = 40
        }
      }
    }
  }
}
```

### WAF Custom (adicionar em main.tf)

```hcl
resource "cloudflare_ruleset" "waf_custom" {
  zone_id = var.zone_id
  name    = "Tribultz Custom WAF Rules"
  kind    = "zone"
  phase   = "http_request_firewall_custom"

  rules {
    action     = "block"
    enabled    = true
    expression = <<-EOT
      (cf.client.bot) and
      not (cf.verified_bot_category in {"Search Engine Crawler" "Monitoring & Analytics"})
    EOT
  }

  rules {
    action     = "block"
    enabled    = true
    expression = <<-EOT
      (http.request.uri.path contains "/api/v1/") and
      (not http.user_agent matches ".")
    EOT
  }

  rules {
    action     = "block"
    enabled    = true
    expression = <<-EOT
      (http.request.uri.path contains "/api/v1/auth/") and
      (http.request.method eq "POST") and
      (not http.request.headers["content-type"][0] contains "application/json")
    EOT
  }

  rules {
    action     = "managed_challenge"
    enabled    = true
    expression = <<-EOT
      (http.request.uri.path contains "/api/v1/billing/") and
      (ip.geoip.country in {"CN" "RU" "KP" "IR" "BY" "CU"})
    EOT
  }
}
```

### Rate Limiting (adicionar em main.tf)

```hcl
resource "cloudflare_ruleset" "rate_limiting" {
  zone_id = var.zone_id
  name    = "Tribultz Rate Limiting"
  kind    = "zone"
  phase   = "http_ratelimit"

  rules {
    action     = "block"
    enabled    = true
    expression = "(http.request.uri.path contains \"/api/v1/public/calculadora\")"
    ratelimit  { characteristics = ["ip.src"]; period = 60; requests_per_period = 20; mitigation_timeout = 60 }
  }

  rules {
    action     = "block"
    enabled    = true
    expression = "(http.request.uri.path eq \"/api/v1/auth/login\")"
    ratelimit  { characteristics = ["ip.src"]; period = 60; requests_per_period = 5; mitigation_timeout = 300 }
  }

  rules {
    action     = "block"
    enabled    = true
    expression = "(http.request.uri.path eq \"/api/v1/auth/register\")"
    ratelimit  { characteristics = ["ip.src"]; period = 60; requests_per_period = 3; mitigation_timeout = 300 }
  }

  rules {
    action     = "block"
    enabled    = true
    expression = "(http.request.uri.path eq \"/api/v1/auth/forgot-password\")"
    ratelimit  { characteristics = ["ip.src"]; period = 60; requests_per_period = 3; mitigation_timeout = 300 }
  }

  rules {
    action     = "block"
    enabled    = true
    expression = "(http.request.uri.path starts_with \"/api/\")"
    ratelimit  { characteristics = ["ip.src"]; period = 60; requests_per_period = 200; mitigation_timeout = 60 }
  }
}
```

## Critério de upgrade sugerido

Revisar quando qualquer um dos gatilhos abaixo for atingido:
- Tráfego > 10.000 req/dia na API
- Primeiro cliente pagante em produção
- Incidente de bot/scraper detectado nos logs
