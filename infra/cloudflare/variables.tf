variable "cloudflare_api_token" {
  description = "Cloudflare API Token com permissões: Zone:Edit, DNS:Edit (Free tier — Firewall:Edit não necessário)"
  type        = string
  sensitive   = true
}

variable "zone_id" {
  description = "Cloudflare Zone ID para tribultz.com.br (Dashboard → Overview → Zone ID)"
  type        = string
}

variable "api_origin_ip" {
  description = "IP público da VM Magalu Cloud (ex: 177.93.xxx.xxx). Preencher após provisionar."
  type        = string
  default     = "0.0.0.0"  # placeholder — substituir com IP real da Magalu
}

variable "frontend_url" {
  description = "URL do frontend Vercel (para CORS e regras WAF)"
  type        = string
  default     = "https://tribultz.vercel.app"
}

# ── Email Routing ──────────────────────────────────────────────────────────────

variable "account_id" {
  description = "Cloudflare Account ID — Dashboard → URL /accounts/{ID} ou My Profile → API Tokens"
  type        = string
}

variable "email_mickel_dest" {
  description = "Gmail/Outlook do Mickel — recebe: mickel@, dpo@, infra@ e catch-all"
  type        = string
  sensitive   = true
}

variable "email_roberta_dest" {
  description = "Gmail/Outlook da Roberta — recebe: roberta@tribultz.com.br"
  type        = string
  sensitive   = true
}

variable "email_shared_dest" {
  description = "Gmail/Outlook para caixa compartilhada — recebe: suporte@, contato@, financeiro@, marketing@"
  type        = string
  sensitive   = true
}

variable "resend_dkim_value" {
  description = <<-EOT
    Valor TXT DKIM do Resend para tribultz.com.br.
    Como obter:
      1. resend.com → Domains → tribultz.com.br → DNS Records
      2. Seção "Domain Verification / DKIM"
      3. Copiar o valor completo do registro TXT resend._domainkey
    Formato: p=MIGfMA...wIDAQAB (chave pública RSA)
  EOT
  type        = string
  default     = "pendente-copiar-dkim-do-resend"
}

variable "resend_send_mx_value" {
  description = <<-EOT
    Valor MX para send.tribultz.com.br (bounce handling Resend).
    Resend → Domains → tribultz.com.br → seção "Enable Sending / SPF"
    Registro MX com name=send. Formato: feedback-smtp.us-east-1.amazonses.com
  EOT
  type        = string
  default     = "pendente-copiar-mx-send-do-resend"
}

variable "resend_send_spf_value" {
  description = <<-EOT
    Valor TXT SPF para send.tribultz.com.br.
    Resend → Domains → tribultz.com.br → seção "Enable Sending / SPF"
    Registro TXT com name=send. Formato: v=spf1 include:amazonses.com ~all
  EOT
  type        = string
  default     = "pendente-copiar-spf-send-do-resend"
}
