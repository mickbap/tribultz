output "api_dns_name" {
  description = "FQDN do endpoint da API após aplicar o Terraform"
  value       = "https://api.tribultz.com.br"
}

output "api_record_proxied" {
  description = "Se o registro DNS está sendo roteado via Cloudflare (WAF ativo)"
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

output "waf_status" {
  description = "Resumo das proteções Cloudflare ativas"
  value = {
    managed_rules  = "OWASP + Cloudflare Managed Ruleset → block"
    rate_limiting  = "calculadora:20/min, login:5/min, register:3/min, global:200/min"
    ssl_mode       = "Full (Strict) — TLS 1.2+ obrigatório"
    hsts           = "max-age=15768000 (6 meses) + subdomínios + preload"
    bot_protection = "Aggressive bots bloqueados, verified bots permitidos"
  }
}
