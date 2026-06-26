"""Gate de acesso do admin BFF — endpoints exigem autenticação superadmin."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Endpoints de leitura do painel admin (visão top-down). Todos atrás de _require_superadmin.
ADMIN_ENDPOINTS = [
    "/api/v1/admin/me",
    "/api/v1/admin/dashboard",
    "/api/v1/admin/tenants",
    "/api/v1/admin/users",
    "/api/v1/admin/usage",
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
