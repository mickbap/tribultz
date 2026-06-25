"""Testes do init de error tracking (Sentry) — comportamento no-op e ativo."""

from app.config import settings
from app.core import observability


def test_init_sentry_noop_sem_dsn(monkeypatch):
    """Sem SENTRY_DSN → no-op (não inicializa, não lança)."""
    monkeypatch.setattr(settings, "SENTRY_DSN", "")
    assert observability.init_sentry() is False


def test_init_sentry_noop_dsn_em_branco(monkeypatch):
    """DSN só com espaços → tratado como ausente."""
    monkeypatch.setattr(settings, "SENTRY_DSN", "   ")
    assert observability.init_sentry() is False


def test_init_sentry_ativo_com_dsn(monkeypatch):
    """Com DSN válido → inicializa e retorna True, sem lançar."""
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://abc123@o0.ingest.sentry.io/0")
    monkeypatch.setattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.0)
    assert observability.init_sentry() is True


def test_init_sentry_dsn_invalido_nao_derruba(monkeypatch):
    """DSN malformado → captura a exceção e segue sem error tracking (retorna False)."""
    monkeypatch.setattr(settings, "SENTRY_DSN", "isto-nao-e-um-dsn")
    assert observability.init_sentry() is False
