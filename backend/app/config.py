"""Tribultz – application settings (reads from .env / environment).

All secrets and service URLs are read from environment variables.
Defaults are provided only for non-sensitive, development-safe values.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Postgres ──────────────────────────────────────────────
    POSTGRES_DB: str = "tribultz"
    POSTGRES_USER: str = "tribultz"
    POSTGRES_PASSWORD: str
    DATABASE_URL: str

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str

    # ── JWT ───────────────────────────────────────────────────
    JWT_SECRET: str
    JWT_ALG: str = "HS256"
    JWT_EXPIRES_MIN: int = 480

    # ── MinIO / S3 ────────────────────────────────────────────
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    S3_ENDPOINT: str
    S3_REGION: str = "us-east-1"
    S3_FORCE_PATH_STYLE: bool = True
    S3_BUCKET: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str

    # ── HubSpot (pós-venda: dunning/win-back via crm_engagement_crew) ───────
    HUBSPOT_ENABLED: bool = False
    HUBSPOT_PRIVATE_APP_TOKEN: str = ""
    HUBSPOT_API_BASE_URL: str = "https://api.hubapi.com"

    # ── Attio (CRM comercial — prospecção→fechamento, PO-2026-07-CRM-001) ───
    # Domínio separado do HubSpot acima: Attio cobre a esteira comercial
    # (lead→fechado), HubSpot fica isolado no ciclo de vida pós-venda.
    # Sem API key → integração é no-op (mesmo padrão do HubSpot).
    ATTIO_ENABLED: bool = False
    ATTIO_API_KEY: str = ""
    ATTIO_WORKSPACE: str = ""
    ATTIO_DEFAULT_PIPELINE: str = ""
    ATTIO_DEFAULT_STAGE: str = ""
    ATTIO_WEBHOOK_SECRET: str = ""
    # ── Security ────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000,https://tribultz.com.br,https://*.vercel.app"
    ENVIRONMENT: str = "development"  # development | staging | production

    # ── Observabilidade / Sentry (error tracking) ───────────
    # Sem DSN → init é no-op (zero impacto em dev/CI). traces_sample_rate controla apenas o
    # tracing de performance; erros são sempre capturados quando o DSN está presente.
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    SENTRY_RELEASE: str = ""

    # ── GA4 Measurement Protocol (eventos server-side, ex.: purchase) ───────
    # Sem API secret → envio é no-op. O api_secret é criado em:
    # GA4 → Admin → Fluxos de dados → (stream) → Measurement Protocol API secrets.
    GA4_MEASUREMENT_ID: str = "G-KJ986WZ5ZJ"
    GA4_MP_API_SECRET: str = ""

    # ── Cloudflare Analytics (tráfego do site, painel admin) ────────────────
    # Sem token → seção do dashboard degrada graciosamente (sem quebrar o resto).
    # Token: Cloudflare → Meu Perfil → API Tokens → Custom Token
    #   (Zone:Analytics:Read + Zone:Zone:Read, escopo só para o zone abaixo).
    CLOUDFLARE_ANALYTICS_TOKEN: str = ""
    CLOUDFLARE_ZONE_ID: str = "0dca11f87046e628725aba0347548ccf"

    # ── Turnstile (CAPTCHA) ─────────────────────────────────
    TURNSTILE_SECRET_KEY: str = ""
    CAPTCHA_ENABLED: bool = False
    CAPTCHA_VERIFY_URL: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    # ── Email / SMTP ──────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@tribultz.com.br"
    SMTP_FROM_NAME: str = "Tribultz"
    SMTP_TLS: bool = True
    EMAIL_VERIFICATION_ENABLED: bool = False
    FRONTEND_URL: str = "http://localhost:3000"

    # ── Asaas (Payment Gateway) ──────────────────────────────
    ASAAS_API_KEY: str = ""
    ASAAS_ENVIRONMENT: str = "sandbox"  # sandbox | production
    ASAAS_WEBHOOK_TOKEN: str = ""

    # ── LLM / OpenRouter ─────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    # Cadeia de fallback de 7 tiers 100% free vive em app/crews/llm_config.py
    # (DEFAULT_FALLBACK_CHAIN) — não nestas settings, que não são lidas por
    # nenhum código (LLM_FREE_PRIMARY/LLM_FREE_FALLBACK removidas em 17/07/2026).
    # Timeout aumentado para acomodar 7 tiers com backoff (pior caso ~90s)
    CHATOPS_TIMEOUT_SECONDS: int = 120
    CREW_MEMORY_TTL_SECONDS: int = 2_592_000

    # ── GitHub Integration ────────────────────────────────────
    GITHUB_TOKEN: str = ""

    # ── News Publishing (auto-publish via GitHub Actions on merge) ──
    NEWS_PUBLISH_TOKEN: str = ""

    # ── External APIs ─────────────────────────────────────────
    CLASSTRIB_API_URL: str = "https://cff.svrs.rs.gov.br/api/v1/consultas/classTrib"
    # Token institucional da SVRS Conformidade Fácil (#313). Vazio = sem auth
    # (mantém o comportamento atual: API responde 403 e usamos os dados locais).
    # Quando provisionado, vai como secret/env e habilita a sincronização real.
    CLASSTRIB_API_TOKEN: str = ""
    CNPJ_PRIMARY_URL: str = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
    CNPJ_FALLBACK_URL: str = "https://receitaws.com.br/v1/cnpj/{cnpj}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()  # type: ignore
