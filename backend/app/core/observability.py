"""Error tracking de aplicação via Sentry.

Inicialização defensiva e opcional: sem `SENTRY_DSN` configurado, `init_sentry()` é
no-op (zero impacto em desenvolvimento, testes e CI). Falhas na própria inicialização
nunca derrubam o boot da aplicação — observabilidade não pode ser ponto único de falha.

Privacidade (LGPD): `send_default_pii=False` — não enviamos cabeçalhos/corpo da requisição
ao Sentry. O conteúdo do XML fiscal (CNPJ/CPF/itens) não é capturado automaticamente.
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    """Inicializa o Sentry se `SENTRY_DSN` estiver configurado. Retorna True se ativo."""
    dsn = (settings.SENTRY_DSN or "").strip()
    if not dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=settings.ENVIRONMENT,
            release=(settings.SENTRY_RELEASE or None),
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            # Não enviar PII (cabeçalhos/corpo) — dados fiscais são sensíveis (LGPD).
            send_default_pii=False,
            integrations=[StarletteIntegration(), FastApiIntegration()],
        )
        logger.info("Sentry inicializado (environment=%s)", settings.ENVIRONMENT)
        return True
    except Exception as exc:  # pragma: no cover — observabilidade nunca derruba o boot
        logger.warning("Falha ao inicializar Sentry — seguindo sem error tracking: %s", exc)
        return False
