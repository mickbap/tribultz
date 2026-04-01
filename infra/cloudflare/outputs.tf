output "api_dns_name" {
  description = "FQDN do endpoint da API após aplicar o Terraform"
  value       = "https://api.tribultz.com.br"
}

output "api_record_proxied" {
  description = "Se o registro DNS está sendo roteado via Cloudflare (CDN + DDoS ativo)"
  value       = cloudflare_record.api_a.proxied
}

output "health_check_url" {
  description = "URL do health check para configurar no monitoramento Magalu Cloud"
  value       = "https://api.tribultz.com.br/health"
}

output "deep_health_url" {
  description = "URL do deep health check (DB + Redis + Asaas + AI)"
  value       = "https://api.tribultz.com.br/health/deep"
}

output "protection_status" {
  description = "Resumo das proteções Cloudflare ativas (Free Tier)"
  value = {
    ddos_protection = "Automático L3/L4/L7 — sempre ativo no Free"
    ssl_mode        = "Full (Strict) — TLS 1.2+ obrigatório"
    hsts            = "max-age=15768000 (6 meses) + subdomínios + preload"
    cache           = "Bypass em /health* e /api/* — dados fiscais sempre frescos"
    rate_limiting   = "App-level: FastAPI (_rate_limiter, _forgot_limiter, _daily_limiter)"
    waf             = "Desabilitado — requer Pro ($20/mês). Ver PRO_UPGRADE.md"
  }
}
