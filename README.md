# tribultz
Plataforma de compliance e simulaÃ§Ã£o CBS/IBS (Reforma 2026): validaÃ§Ã£o fiscal em tempo real, reconciliaÃ§Ã£o, trilha auditÃ¡vel e dashboard executivo.

## Status Sprint 5 (P0+P1)
- Concluida no repositorio canonical `mickbap/tribultz`.
- Fluxo demo oficial: `Login -> Dashboard -> Chat -> Validar CBS/IBS -> Job -> Audit`.
- Console roda em Mock Mode por padrao (ON) e suporta API Mode.
- Em API Mode, toda request envia `Authorization: Bearer <token>` e `X-Tenant-Id: <tenant>`.
- Login real depende de backend/credenciais validos no ambiente.
- `mickbap/tribultz-console-navigator` fica somente como referencia/export do Lovable (nao canonical).

## Status Sprint 6 (P0)
- Validacao XML com evidencias auditaveis em `/validate-xml` (NFS-e primeiro, NF-e suportado).
- Contrato Findings + Evidence v1.1 implementado (types + schema + example payload).
- Regras MVP aplicadas (FATAL: CST/cClassTrib/CodigoServico; ALERT: NCM e beneficios/creditos).
- Workflow de excecao implementado em `/exceptions` (OPEN -> APPROVED/REJECTED) com eventos no audit.
<!-- SPRINT4-START -->
## Runbook rapido (Dev/QA) - Chat Fiscal MVP

### Portas
- API: http://localhost:8000 (docs: /docs, OpenAPI: /openapi.json)
- Console: http://localhost:3000
- MinIO: http://localhost:9000 (health: /minio/health/ready)

### Stack (infra)
~~~bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps
~~~

### Backend gate (source of truth)
~~~bash
docker compose -f infra/docker-compose.yml run --rm -T api sh -lc "set -euxo pipefail; pip install -q ruff pyright; ruff check app tests; pyright; pytest -q"
~~~

### Frontend gate
~~~bash
cd frontend
npm ci
npm run build
~~~

### Auth/JWT (sem expor token)
Crie `.secrets/auth.json` (fora do git):

~~~json
{"email":"SEU_EMAIL","password":"SUA_SENHA","tenant_slug":"SEU_TENANT"}
~~~

Gere token via `POST /api/v1/auth/login` e salve `.secrets/chat_jwt.txt` com:

~~~text
Bearer <access_token>
~~~

### E2E (contrato + evidencia)
- UI: http://localhost:3000/chat
- Mensagem: `Validate invoice INV-999 base 100.00 CBS 0 IBS 0`
- Confirmar evidence com link `/jobs/<id>` e abrir Job/Audit.

### Seguranca (Jobs anti-IDOR)
Endpoints de Jobs sao tenant-scoped; tenants diferentes nao listam nem acessam jobs uns dos outros.
<!-- SPRINT4-END -->


