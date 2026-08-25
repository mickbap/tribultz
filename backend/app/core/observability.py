"""Error tracking de aplicação via Sentry.

Inicialização defensiva e opcional: sem `SENTRY_DSN` configurado, `init_sentry()` é
no-op (zero impacto em desenvolvimento, testes e CI). Falhas na própria inicialização
nunca derrubam o boot da aplicação — observabilidade não pode ser ponto único de falha.

Privacidade (LGPD): `send_default_pii=False` — não enviamos cabeçalhos/corpo da requisição
ao Sentry. O conteúdo do XML fiscal (CNPJ/CPF/itens) não é capturado automaticamente.
"""

from __future__ import annotations

import logging
from typing import Literal

from app.config import settings

#: Níveis aceitos pelo `sentry_sdk.capture_message`.
AlertLevel = Literal["debug", "info", "warning", "error", "fatal"]

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    """Inicializa o Sentry se `SENTRY_DSN` estiver configurado. Retorna True se ativo."""
    dsn = (settings.SENTRY_DSN or "").strip()
    if not dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=settings.ENVIRONMENT,
            release=(settings.SENTRY_RELEASE or None),
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            # Não enviar PII (cabeçalhos/corpo) — dados fiscais são sensíveis (LGPD).
            send_default_pii=False,
            # FastAPI/Starlette cobrem a API; Celery cobre worker e beat (tasks de fundo).
            integrations=[StarletteIntegration(), FastApiIntegration(), CeleryIntegration()],
        )
        logger.info("Sentry inicializado (environment=%s)", settings.ENVIRONMENT)
        return True
    except Exception as exc:  # pragma: no cover — observabilidade nunca derruba o boot
        logger.warning("Falha ao inicializar Sentry — seguindo sem error tracking: %s", exc)
        return False


def capture_alert(
    message: str,
    *,
    level: AlertLevel = "warning",
    extra: dict | None = None,
) -> bool:
    """Envia um alerta operacional ao Sentry e ao log. Retorna True se foi ao Sentry.

    Existe (#673) para que o caminho do alerta seja EXPLÍCITO e testável. Depender
    da integração implícita `logging`→Sentry deixa a entrega indemonstrável: não dá
    para provar, em teste, que o plantão seria notificado.

    Defensiva como o resto deste módulo: sem DSN é no-op silencioso (só log), e
    falha na captura nunca propaga — alerta não pode derrubar quem alerta.
    """
    log = logger.error if level == "error" else logger.warning
    log("%s | %s", message, extra or {})

    if not (settings.SENTRY_DSN or "").strip():
        return False
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for chave, valor in (extra or {}).items():
                scope.set_extra(chave, valor)
            sentry_sdk.capture_message(message, level=level)
        return True
    except Exception as exc:  # pragma: no cover — observabilidade nunca derruba nada
        logger.warning("Falha ao enviar alerta ao Sentry: %s", exc)
        return False
