"""Gate de acesso do admin BFF — endpoints exigem autenticação superadmin."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Endpoints de leitura do painel admin (visão top-down) + audit log. Todos superadmin-only.
ADMIN_ENDPOINTS = [
    "/api/v1/admin/me",
    "/api/v1/admin/dashboard",
    "/api/v1/admin/tenants",
    "/api/v1/admin/users",
    "/api/v1/admin/usage",
    "/api/v1/admin/audit-log",
]

# Ações administrativas (mutações) — Fase 2. UUID fictício; o gate barra antes de tudo.
_UUID = "00000000-0000-0000-0000-000000000000"
ADMIN_ACTIONS = [
    f"/api/v1/admin/users/{_UUID}/active",
    f"/api/v1/admin/tenants/{_UUID}/active",
]


def test_admin_endpoints_exigem_autenticacao():
    """Sem token → 401/403 (nunca 200). Não vaza dado de plataforma a anônimo."""
    for path in ADMIN_ENDPOINTS:
        resp = client.get(path)
        assert resp.status_code in (401, 403), f"{path} deveria bloquear anônimo, veio {resp.status_code}"


def test_admin_endpoints_registrados():
    """As rotas existem (não 404) — o gate responde com 401/403, não com rota inexistente."""
    for path in ADMIN_ENDPOINTS:
        assert client.get(path).status_code != 404, f"{path} não registrado"


def test_admin_acoes_exigem_autenticacao():
    """Mutações (suspender/reativar) bloqueadas para anônimo — nunca executam sem superadmin."""
    for path in ADMIN_ACTIONS:
        resp = client.post(path, json={"is_active": False})
        assert resp.status_code in (401, 403), f"{path} deveria bloquear anônimo, veio {resp.status_code}"
