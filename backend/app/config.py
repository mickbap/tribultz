"""Tribultz – application settings (reads from .env / environment).

All secrets and service URLs are read from environment variables.
Defaults are provided only for non-sensitive, development-safe values.
"""

from typing import ClassVar

from pydantic import model_validator
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

    # ── Rumy (AI SDR — handoff comercial, Rounds 4–5 da PO-2026-07-CRM-001) ─
    # Flags OFF por padrão e nenhum efeito externo: com RUMY_WEBHOOK_ENABLED
    # off o endpoint /api/v1/webhooks/rumy responde 404; com
    # HANDOFF_APPLY_ENABLED off o worker opera em shadow mode (ledger sem
    # aplicar). Supressão real no Rumy (F5) e handoff automático seguem
    # bloqueados. Regra fail-safe transversal: desligar qualquer flag NUNCA
    # re-permite outbound — a permissão é conjuntiva e a proteção de pessoa
    # (DEC-5) persiste independente de flag.
    #: Teto aplicacional do corpo do webhook Rumy. O nginx da VM permite 50M
    #: (infra/scripts/magalu-init.sh) — folgado demais para um webhook. Não
    #: confiar em Content-Length: cliente hostil omite ou mente.
    RUMY_MAX_BODY_BYTES: int = 1_048_576
    RUMY_WEBHOOK_ENABLED: bool = False
    HANDOFF_APPLY_ENABLED: bool = False
    RUMY_SUPPRESSION_ENABLED: bool = False
    RUMY_WEBHOOK_SECRET: str = ""
    # UUID do tenant operacional interno que recebe os handoffs (Round 4 §11:
    # tenant é resolvido no ingest, nunca confiado ao produtor). Vazio ⇒ o
    # endpoint responde 503 (fail-closed).
    HANDOFF_TENANT_ID: str = ""
    # SLAs provisórios do piloto (Rounds 6 §8 e 7 §2/DEC-6 — três relógios
    # INDEPENDENTES, horas úteis): pausa manual no Rumy ≤ 5 min (contenção —
    # a janela de exposição do Caminho C); HANDOFF_REQUESTED→HUMAN_OWNED ≤ 15
    # min (ownership); HUMAN_OWNED→1ª ação substantiva ≤ 30 min (atendimento).
    # "Assumir" não satisfaz nem o 1º nem o 3º.
    HANDOFF_PAUSE_SLA_MINUTES: int = 5
    HANDOFF_ACCEPT_SLA_MINUTES: int = 15
    HANDOFF_FIRST_ACTION_SLA_MINUTES: int = 30
    # Lista de plantão do alerta de pausa (CSV de e-mails; Round 7 §7). Nomes e
    # canal são decisão de Produto; vazio ⇒ alerta fica só no audit/log.
    HANDOFF_ALERT_EMAILS: str = ""

    # ── Frescor do dado regulatório cClassTrib (#673) ───────
    # O motor valida contra a tabela SVRS embarcada; se o classtrib-sync parar, o
    # produto segue 200 servindo tabela velha. Thresholds calibrados pela cadência
    # real da fonte (a SVRS adiciona códigos com frequência — +8 em 2 dias) e pela
    # flakiness conhecida do portal (~30% das execuções diárias falham por timeout):
    # indisponibilidade pontual da fonte NÃO degrada sozinha, só combinada com dado
    # velho. TTL protege a fonte pública de ser martelada pelo /health/deep.
    #
    # Default OFF, como as demais integrações da casa (HUBSPOT_ENABLED,
    # ATTIO_ENABLED, RUMY_WEBHOOK_ENABLED): a probe faz chamada de saída para um
    # portal público de governo. Ligar por acidente em dev/CI significaria bater
    # nessa fonte a cada execução de teste. Produção liga explicitamente no .env.
    CLASSTRIB_FRESHNESS_ENABLED: bool = False
    CLASSTRIB_FRESHNESS_WARN_DAYS: int = 7
    CLASSTRIB_FRESHNESS_FAIL_DAYS: int = 21
    CLASSTRIB_FRESHNESS_TTL_SECONDS: int = 900

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

    #: Ambientes reconhecidamente NÃO produtivos. Tudo que não estiver aqui —
    #: inclusive vazio, ausente, `staging`, `prod`, `Production` ou um typo — é
    #: tratado com postura restritiva. A lista de exceções é a dos ambientes
    #: seguros, nunca a dos perigosos: allowlist de aliases produtivos falharia
    #: aberto no primeiro nome novo que ninguém lembrasse de cadastrar.
    NON_PRODUCTION_ENVIRONMENTS: ClassVar[frozenset[str]] = frozenset(
        {"development", "test", "ci", "local"}
    )

    def is_production_posture(self) -> bool:
        """Postura restritiva? Qualquer coisa fora da allowlist responde True."""
        return (self.ENVIRONMENT or "").strip().lower() not in self.NON_PRODUCTION_ENVIRONMENTS

    @model_validator(mode="after")
    def _postura_restritiva_exige_observabilidade_regulatoria(self):
        """Gate: fora de dev/test/ci/local, não se sobe sem frescor regulatório (#673).

        O default é OFF para proteger dev/CI de chamar um portal de governo. Sem
        este gate, o mesmo default faria produção subir SILENCIOSAMENTE sem
        observabilidade da dependência regulatória — exatamente o defeito que a
        issue existe para fechar, reintroduzido pela porta dos fundos.

        Round 3: a checagem anterior era `ENVIRONMENT == "production"`, igualdade
        exata. `prod`, `Production`, ` production `, vazio e ausente passavam
        direto — 11 de 12 variantes testadas subiam cegas. Agora o desconhecido
        endurece em vez de afrouxar.

        Falha no boot é deliberada: é barulhenta, aparece no deploy e não deixa
        ninguém descobrir meses depois que o sinal nunca esteve ligado.
        """
        if self.is_production_posture() and not self.CLASSTRIB_FRESHNESS_ENABLED:
            raise ValueError(
                f"CLASSTRIB_FRESHNESS_ENABLED deve ser true em ENVIRONMENT="
                f"{self.ENVIRONMENT!r} (postura restritiva) — sem isso o produto serve "
                f"tabela cClassTrib potencialmente desatualizada sem nenhum sinal de "
                f"saúde (#673). Ambientes livres: "
                f"{sorted(self.NON_PRODUCTION_ENVIRONMENTS)}."
            )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()  # type: ignore
