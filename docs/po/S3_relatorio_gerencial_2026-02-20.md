# Relatorio Gerencial - Sprint 3 (Chat MVP Fiscal)
**Data:** 20/02/2026  
**Branch:** feat/sprint3-chat-mvp  
**Contexto:** entrega do fluxo MVP de chat fiscal com rastreabilidade (evidence -> Job) e gates (lint/typing/tests) verdes.

## 1) Visao Executiva
A Sprint 3 consolidou o **fluxo ponta-a-ponta do Chat Fiscal (MVP)**:
- API **/api/v1/chat/message** com contrato estavel (conversation_id, response_markdown, evidence tipada).
- Execucao assincrona via worker (Task A) com **Job persistido e consultavel**.
- Seguranca reforcada: **tenant-scope** aplicado para evitar IDOR em Jobs.
- Infra local via Docker (db/redis/minio/api/worker/beat) e build do Console (Next.js) validados.

## 2) Entregas Confirmadas (o que esta pronto)
### Backend (Fiscal/Tributario)
- **Chat MVP** com mensagem de validacao (ex.: "Validate invoice INV-999 ...") retornando:
  - `conversation_id`
  - `response_markdown`
  - `evidence[]` com item `type=job` e `href=/jobs/<id>`
- **Jobs persistentes**:
  - criacao de linha `jobs` no momento do trigger (chat/executor)
  - atualizacao de status no worker (RUNNING/SUCCESS/FAILED)
  - endpoints:
    - `GET /api/v1/jobs` (lista por tenant)
    - `GET /api/v1/jobs/{job_id}` (detail por tenant)
    - `POST /api/v1/jobs/{job_id}/reprocess` (por tenant)
- **Anti-IDOR** comprovado:
  - Tenant B nao le/lista jobs do Tenant A (404 + listagem vazia).

### Qualidade (gates)
- **ruff**: OK
- **pyright**: 0 errors
- **pytest**: 10 passed (3 warnings de deprecacao - nao bloqueantes)
- **E2E Smoke**:
  - /auth/login -> token -> /chat/message -> evidence(job) -> /jobs OK

### Frontend (Console)
- Build reprodutivel passou: `npm ci` + `npm run build`
- UI acessivel em `http://localhost:3000/chat` (Next dev/prod conforme ambiente)

## 3) Evidencias de Execucao (resumo)
- Infra: db/redis/minio healthy; api/worker/beat up
- API:
  - `GET /openapi.json` HTTP 200
  - `GET /docs` HTTP 200
- Front:
  - `GET /chat` HTTP 200
- Jobs:
  - `GET /api/v1/jobs` retorna itens do tenant atual
  - `GET /api/v1/jobs/{id}` retorna SUCCESS/FAIL conforme task

## 4) Riscos / Debitos Tecnicos (priorizados)
1) **DDL runtime de jobs** (criacao de tabela via codigo) - risco medio  
   - Mitigacao S4: migrar para **Alembic** e remover DDL em runtime.
2) **CI (GitHub Actions) reprovando** - blocker para merge rapido  
   - Suspeitas comuns: mismatch de Node/Python, steps de docker/compose, cache, servicos.
3) **Warnings de deprecacao** (pydantic/passlib/crypt) - baixo  
   - Mitigacao: upgrade planejado e ajuste gradual.

## 5) Recomendacao de Go/No-Go
**GO** para Sprint 4 (com ressalva de CI): tecnicamente o MVP esta integro (gates + seguranca + E2E).  
**Proximo foco imediato:** estabilizar CI e formalizar runbooks/DoD.
