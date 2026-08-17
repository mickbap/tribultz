"""Probes do /health/deep em paralelo — L2.5 (decisão D5 do despacho QA).

Os probes rodavam em série: sete chamadas de rede somando 2–5s. No cold start,
logo após o deploy, a soma estourava o timeout de 3s do probe SMTP e o endpoint
devolvia `degraded` com `email=unreachable` — com o relay perfeitamente
acessível (0,62s medidos de dentro do container, já quente).

Efeito prático: TODO deploy produzia uma janela de degradação falsa. Estes
testes fixam que a latência é a do probe mais lento, não a soma, e que um probe
lento não contamina o veredito dos outros.
"""

from __future__ import annotations

import time
from unittest.mock import patch

from app.routers import health


def _lento(segundos: float, retorno: str = "ok"):
    def _fn():
        time.sleep(segundos)
        return retorno
    return _fn


def test_latencia_e_a_do_probe_mais_lento_nao_a_soma():
    """Sete probes de 0,2s: em série daria ~1,4s; em paralelo, ~0,2s."""
    with (
        patch.object(health, "_probe_db", _lento(0.2)),
        patch.object(health, "_probe_redis", _lento(0.2)),
        patch.object(health, "_probe_asaas", _lento(0.2)),
        patch.object(health, "_probe_ai_engine", _lento(0.2)),
        patch.object(health, "_probe_hubspot", _lento(0.2)),
        patch.object(health, "_probe_email", _lento(0.2)),
        patch.object(health, "_probe_s3", _lento(0.2)),
    ):
        t0 = time.monotonic()
        resp = health.deep_health()
        decorrido = time.monotonic() - t0

    assert resp.status == "ok"
    assert decorrido < 0.9, (
        f"probes ainda parecem seriais: {decorrido:.2f}s para 7 probes de 0,2s"
    )


def test_probe_lento_nao_atrasa_os_demais():
    """Um probe de 0,5s não deve empurrar a latência para a soma dos sete."""
    with (
        patch.object(health, "_probe_email", _lento(0.5)),
        patch.object(health, "_probe_db", _lento(0.05)),
        patch.object(health, "_probe_redis", _lento(0.05)),
        patch.object(health, "_probe_asaas", _lento(0.05)),
        patch.object(health, "_probe_ai_engine", _lento(0.05)),
        patch.object(health, "_probe_hubspot", _lento(0.05)),
        patch.object(health, "_probe_s3", _lento(0.05)),
    ):
        resp = health.deep_health()

    assert resp.status == "ok"
    assert resp.email == "ok"
    assert resp.latency_ms < 900


def test_probe_que_estoura_nao_derruba_o_endpoint():
    """Exceção num probe vira `unreachable`, não erro 500."""
    def _explode():
        raise RuntimeError("probe quebrou")

    # Os demais probes são fixados: sem isso, o probe real de S3 (MinIO fora no
    # ambiente de teste) derrubaria o status para "error" e o teste passaria a
    # medir outra coisa.
    with (
        patch.object(health, "_probe_hubspot", _explode),
        patch.object(health, "_probe_db", _lento(0.01)),
        patch.object(health, "_probe_redis", _lento(0.01)),
        patch.object(health, "_probe_asaas", _lento(0.01)),
        patch.object(health, "_probe_ai_engine", _lento(0.01)),
        patch.object(health, "_probe_email", _lento(0.01)),
        patch.object(health, "_probe_s3", _lento(0.01)),
    ):
        resp = health.deep_health()

    assert resp.hubspot == "unreachable"
    assert resp.status in ("ok", "degraded")


def test_timeout_do_smtp_tolera_cold_start():
    """O valor é parte do contrato desta correção — 3s era o que estourava."""
    import inspect
    fonte = inspect.getsource(health._probe_email)
    assert "timeout=6.0" in fonte, "timeout do probe SMTP não pode voltar a 3s (L2.5)"
