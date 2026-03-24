"""Tribultz – application settings (reads from .env / environment).

All secrets and service URLs are read from environment variables.
Defaults are provided only for non-sensitive, development-safe values.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Postgres ──────────────────────────────────────────────
    POSTGRES_DB: str = "tribultz"
    POSTGRES_USER: str = "tribultz"
    POSTGRES_PASSWORD: str = ""  # REQUIRED: set via env or .env
    DATABASE_URL: str = "postgresql+psycopg2://tribultz:changeme@localhost:5432/tribultz"  # Override via env or .env

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"

    # ── JWT ───────────────────────────────────────────────────
    JWT_SECRET: str = ""  # REQUIRED: set via env or .env (min 32 chars)
    JWT_ALG: str = "HS256"
    JWT_EXPIRES_MIN: int = 480

    # ── MinIO / S3 ────────────────────────────────────────────
    MINIO_ROOT_USER: str = ""  # REQUIRED: set via env or .env
    MINIO_ROOT_PASSWORD: str = ""  # REQUIRED: set via env or .env
    S3_ENDPOINT: str = "http://minio:9000"
    S3_BUCKET: str = "tribultz"
    S3_ACCESS_KEY: str = ""  # REQUIRED: set via env or .env
    S3_SECRET_KEY: str = ""  # REQUIRED: set via env or .env

    # ── HubSpot ───────────────────────────────────────────────
    HUBSPOT_ENABLED: bool = False
    HUBSPOT_PRIVATE_APP_TOKEN: str = ""
    HUBSPOT_API_BASE_URL: str = "https://api.hubapi.com"
    CHATOPS_TIMEOUT_SECONDS: int = 45

    # ── Security ────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"  # development | staging | production

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
    LLM_FREE_PRIMARY: str = "openrouter/google/gemini-2.0-flash-exp:free"
    LLM_FREE_FALLBACK: str = "openrouter/qwen/qwen3-coder-480b-a35b-instruct:free"
    LLM_PAID_FALLBACK: str = "openrouter/anthropic/claude-3-5-sonnet"

    # ── External APIs ─────────────────────────────────────────
    CLASSTRIB_API_URL: str = "https://cff.svrs.rs.gov.br/api/v1/consultas/classTrib"
    CNPJ_PRIMARY_URL: str = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
    CNPJ_FALLBACK_URL: str = "https://receitaws.com.br/v1/cnpj/{cnpj}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
