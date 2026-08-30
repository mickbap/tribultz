"""Guards do descomissionamento do Attio (ROUND 18-A).

O Attio deixou de fazer parte da arquitetura operacional da Tribultz. Este
arquivo é o que sobra dos sete `test_attio_*` originais: em vez de exercitar a
integração, ele prova que ela não voltou.

Fora do escopo destes guards, DE PROPÓSITO: as colunas históricas
``attio_person_id`` / ``attio_company_id`` / ``attio_deal_id`` de
``crm_lead_links``. Elas são dado preservado para auditoria, não integração —
removê-las é decisão separada, com migration própria.
"""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_webhook_attio_desmontado_retorna_404():
    """O endpoint respondia 200 em produção a corpo não assinado, sem gate de
    flag. Se voltar a existir, este guard falha."""
    for header in ("attio-signature", "x-attio-signature"):
        r = client.post(
            "/api/v1/webhooks/attio",
            content=b'{"events":[]}',
            headers={header: "qualquer", "content-type": "application/json"},
        )
        assert r.status_code == 404, (
            "router Attio voltou a ser montado — o descomissionamento do "
            "ROUND 18-A exige que esta rota nao exista"
        )


def test_nenhuma_rota_attio_registrada_no_app():
    rotas = [getattr(r, "path", "") for r in app.routes]
    ofensores = [p for p in rotas if "attio" in p.lower()]
    assert not ofensores, "ha rota com 'attio' no path: %s" % ofensores


def test_pacote_de_integracao_attio_nao_existe():
    for mod in ("app.integrations.attio", "app.integrations.attio.client"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod)


def test_settings_nao_expoe_nenhuma_variavel_attio():
    """Config sem ATTIO_* é o que permite remover os secrets da VM depois."""
    from app.config import Settings

    ofensores = [f for f in Settings.model_fields if "ATTIO" in f.upper()]
    assert not ofensores, "Settings voltou a expor variavel Attio: %s" % ofensores
