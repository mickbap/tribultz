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
  content = var.api_origin_ip
  type    = "A"
  proxied = true
  ttl     = 1  # Auto (gerenciado pela Cloudflare quando proxied=true)
  comment = "Tribultz API — Magalu Cloud VM"
}

# tribultz.com.br (apex) → Vercel
# Cloudflare CNAME Flattening resolve o apex automaticamente
resource "cloudflare_record" "apex_cname" {
  zone_id         = var.zone_id
  name            = "@"
  content         = "cname.vercel-dns.com"
  type            = "CNAME"
  proxied         = true
  ttl             = 1
  allow_overwrite = true
  comment         = "Frontend Vercel — apex domain (CNAME Flattening)"
}

# www.tribultz.com.br → redireciona para tribultz.com.br (canônico)
# Redirect 308 configurado no painel Vercel (permanente, preserva método)
resource "cloudflare_record" "www_cname" {
  zone_id         = var.zone_id
  name            = "www"
  content         = "cname.vercel-dns.com"
  type            = "CNAME"
  proxied         = true
  ttl             = 1
  allow_overwrite = true
  comment         = "Frontend Vercel — www redireciona para apex via Vercel (308)"
}

# ── SSL/TLS + Segurança ───────────────────────────────────────────────────────
# NOTA: zone_settings_override requer permissão "Zone Settings: Edit" no API Token.
# O token atual usa template "Edit zone DNS" que não inclui essa permissão.
#
# Configurar MANUALMENTE no painel Cloudflare → tribultz.com.br → SSL/TLS:
#   ✅ SSL/TLS: Full (strict)
#   ✅ Always Use HTTPS: On
#   ✅ HSTS: max-age=15768000, includeSubDomains, preload
#   ✅ Minimum TLS: 1.2
#   ✅ TLS 1.3: On
#   ✅ HTTP/2: On | HTTP/3: On | Brotli: On
#   ✅ Security Level: Medium
#
# Para gerenciar via Terraform no futuro: adicionar permissão "Zone Settings: Edit"
# ao token em: dash.cloudflare.com/profile/api-tokens → editar token atual

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

# ── Email Routing ──────────────────────────────────────────────────────────────
# Cloudflare Email Routing — 8 aliases @tribultz.com.br + catch-all
#
# AÇÃO MANUAL OBRIGATÓRIA antes de aplicar as regras:
#   Cloudflare Dashboard → tribultz.com.br → Email → Email Routing → Enable
#   (cloudflare_email_routing_settings requer permissão especial não disponível
#    no template "Edit zone DNS". Habilitado manualmente uma única vez.)
#
# Pós-apply:
#   1. mickel.tribultz@gmail.com e roberta.tribultz@gmail.com receberão
#      e-mail de verificação da Cloudflare — clicar no link
#   2. Para responder como @tribultz.com.br: Gmail → Configurações →
#      Contas → Enviar como → SMTP smtp.resend.com:587, user=resend,
#      senha=re_391k65v8_QFQ4w3SS2UcjcfnLmjzjGJHS
# ─────────────────────────────────────────────────────────────────────────────

# ── Endereços de destino verificados ─────────────────────────────────────────
# NOTA: mickel e shared usam o mesmo Gmail → apenas um recurso (shared)
# Cloudflare não permite dois registros com o mesmo e-mail de destino.

resource "cloudflare_email_routing_address" "roberta" {
  account_id = var.account_id
  email      = var.email_roberta_dest
}

resource "cloudflare_email_routing_address" "shared" {
  account_id = var.account_id
  email      = var.email_shared_dest
}

# ── Regras de roteamento — gerenciadas via Cloudflare Dashboard ───────────────
# As regras abaixo são configuradas manualmente em:
#   tribultz.com.br → Email → Email Routing → Regras de roteamento
#
# Razão: cloudflare_email_routing_rule requer permissões de API não disponíveis
# em tokens de zona padrão (Authentication error 10000).
#
# Regras configuradas no dashboard:
#   mickel@      → mickel.tribultz@gmail.com
#   roberta@     → roberta.tribultz@gmail.com
#   suporte@     → mickel.tribultz@gmail.com
#   contato@     → mickel.tribultz@gmail.com
#   financeiro@  → mickel.tribultz@gmail.com
#   marketing@   → mickel.tribultz@gmail.com
#   dpo@         → mickel.tribultz@gmail.com
#   infra@       → mickel.tribultz@gmail.com
#   catch-all    → mickel.tribultz@gmail.com

# ── MX + DKIM Email Routing — gerenciados pela Cloudflare ────────────────────
# Os registros MX (route1/2/3.mx.cloudflare.net) e o DKIM (cf2024-1._domainkey)
# são adicionados automaticamente pela Cloudflare ao habilitar Email Routing via
# Dashboard → Email → Email Routing → "Adicionar Registros e Habilitar".
# NÃO gerenciar via Terraform — são infraestrutura interna da Cloudflare.

# ── SPF — Receber (Cloudflare Routing) + Enviar (Resend) ─────────────────────
# SPF único no apex: inclui ambos os provedores.
# Cloudflare CNAME Flattening permite TXT no @ mesmo com CNAME para Vercel.

resource "cloudflare_record" "spf" {
  zone_id = var.zone_id
  name    = "@"
  content = "v=spf1 include:_spf.mx.cloudflare.net ~all"
  type    = "TXT"
  proxied = false
  ttl     = 3600
  comment = "SPF root: apenas Cloudflare Email Routing (inbound). Resend usa send.tribultz.com.br"
}

# ── DKIM — Resend ─────────────────────────────────────────────────────────────
# Tipo TXT (não CNAME) — valor gerado pelo Resend em Domains → tribultz.com.br
# Colar o valor completo p=MIGfMA...wIDAQAB no terraform.tfvars

resource "cloudflare_record" "resend_dkim" {
  zone_id = var.zone_id
  name    = "resend._domainkey"
  content = var.resend_dkim_value
  type    = "TXT"
  proxied = false
  ttl     = 3600
  comment = "DKIM Resend — assina e-mails do noreply@tribultz.com.br"
}

# ── SPF + MX do subdomínio send.tribultz.com.br (Resend envelope sender) ──────
# Resend usa send.tribultz.com.br como Return-Path (envelope sender).
# O SPF é verificado neste subdomínio, não no root.
# DMARC passa com aspf=r (relaxed) pois o domínio organizacional coincide.

resource "cloudflare_record" "resend_send_mx" {
  zone_id  = var.zone_id
  name     = "send"
  content  = var.resend_send_mx_value
  type     = "MX"
  proxied  = false
  ttl      = 3600
  priority = 10
  comment  = "MX Resend — bounce handling para send.tribultz.com.br"
}

resource "cloudflare_record" "resend_send_spf" {
  zone_id = var.zone_id
  name    = "send"
  content = var.resend_send_spf_value
  type    = "TXT"
  proxied = false
  ttl     = 3600
  comment = "SPF Resend — autoriza envio via send.tribultz.com.br"
}

# ── DMARC ─────────────────────────────────────────────────────────────────────
# Fase 1 — p=none: monitorar sem bloquear (primeiras 2-4 semanas)
#   → Acompanhar relatórios em dpo@ para confirmar que SPF + DKIM estão OK
# Fase 2 — mudar para p=quarantine após confirmar zero falsos positivos
# Fase 3 — mudar para p=reject quando 100% dos envios forem autenticados
#
# aspf=r (relaxed): Return-Path send.tribultz.com.br ≈ From tribultz.com.br ✅
# rua: relatórios agregados diários → dpo@
# ruf: relatórios forenses (por e-mail falho) → infra@

resource "cloudflare_record" "dmarc" {
  zone_id = var.zone_id
  name    = "_dmarc"
  content = "v=DMARC1; p=none; rua=mailto:dpo@tribultz.com.br; ruf=mailto:infra@tribultz.com.br; fo=1; adkim=s; aspf=r; pct=100"
  type    = "TXT"
  proxied = false
  ttl     = 3600
  comment = "DMARC fase 1 — p=none (monitorar). Evoluir: none → quarantine → reject"
}
