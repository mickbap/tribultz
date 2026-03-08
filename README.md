# tribultz
Plataforma de compliance e simulaÃ§Ã£o CBS/IBS (Reforma 2026): validaÃ§Ã£o fiscal em tempo real, reconciliaÃ§Ã£o, trilha auditÃ¡vel e dashboard executivo.

## Status atual (2026-03-08)
- Sprint 6 encerrada com release `sprint-6-crewai-runtime-v1`.
- PRs de fechamento mergeadas em `main`: #32 (CrewAI runtime hardening) e #30 (discovery scaffold).
- Sprint 5 permanece disponivel via release `sprint-5-console-v2`.
- Fluxo demo oficial mantido: `Login -> Dashboard -> Chat -> Validar CBS/IBS -> Job -> Audit`.
- Console roda em Mock Mode por padrao (ON) e suporta API Mode.
- Em API Mode, toda request envia `Authorization: Bearer <token>` e `X-Tenant-Id: <tenant>`.

## Sprint 7 (North Star)
- North Star: transformar discovery da Roberta em regras deterministicas auditaveis sem quebrar o contrato Findings/Evidence v1.1.
- Backlog ativo S7:
  - #37 `[S7-01]` Pacote de 3 XML anonimizados + gabarito validado.
  - #34 `[S7-02]` Top 10 rules phase 1 no motor (deterministico + evidencias).
  - #35 `[S7-03]` Cobertura de variacoes de paths NFS-e.
  - #33 `[S7-04]` Runbook S7 + criterios de aceite QA.
- Carryover de discovery (migrado para S7): #13 e #21.
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


