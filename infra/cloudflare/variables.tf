variable "cloudflare_api_token" {
  description = "Cloudflare API Token com permissões: Zone:Edit, Firewall:Edit, DNS:Edit"
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
