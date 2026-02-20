# Sprint 4 - Kickoff Pack (Insumos para Execucao)
**Data:** 20/02/2026  
**Janela de trabalho (hoje):** 04:00-07:00 (execucao focada e objetiva)

## 1) Meta da Sprint 4
Elevar o MVP para padrao producao em governanca:
- **QA automatizado (CrewAI)** + contract checks + seguranca
- **Padrao de resposta tributaria BR (PT-BR, BRL, rastreabilidade)**
- **Login/UX robusto** (preparacao p/ MFA/SSO)
- **CI confiavel** (Actions verdes)

## 2) Escopo (In/Out)
### IN (prioridade)
1) **S4-01 QA Specialist Agent (gates automaticos)**
2) **S4-02 Template de respostas tributarias BR**
3) **Correcao de CI (workflows)** - prioridade operacional
4) Hardening minimo: rate limit/login + auditoria basica (se couber)

### OUT (jogar para S5 se necessario)
- MFA TOTP completo
- SSO OIDC/SAML completo
- WebAuthn/Passkeys

## 3) Backlog Prioritario (com DoD)
### S4-01 - QA Specialist Agent (CrewAI)
**DoD:**
- `qa_specialist` em `crews/.../agents.yaml`
- task `qa_validate_gates` em `crews/.../tasks.yaml`
- relatorio Markdown com PASS/FAIL por gate + falhas + risco + recomendacao
- checagens minimas:
  - 401 sem token
  - 404 cross-tenant (jobs e conversa, quando aplicavel)
  - 422 message > 4k
  - 429 rate limit
  - evidence tipada
  - ruff/pyright/pytest
  - frontend build

### S4-02 - Padrao de resposta tributaria BR
**DoD:**
- template Markdown aplicado ao fluxo validate
- BRL: `R$ 1.234,56`
- secoes minimas: Resultado, Evidencias, Observacoes/Premissas
- evidencia sempre tipada + Job link interno

### S4-03 - UX de Login Cliente
**DoD:**
- /login com loading/erro/bloqueio temporario
- persistencia segura de sessao (avaliar cookie httpOnly vs token storage)
- redirect pos-login com allowlist (anti-open-redirect)
- rate limit no login + auditoria (login_succeeded/failed/logout)

## 4) Runbook (Execucao diaria)
### Infra
- `docker compose -f infra/docker-compose.yml up -d`
- validar `ps` + healthchecks (db/redis/minio)

### Backend Gate (source of truth)
- `docker compose -f infra/docker-compose.yml run --rm -T api sh -lc "pip install -q ruff pyright; ruff check app tests; pyright; pytest -q"`

### Frontend Gate
- `cd frontend; npm ci; npm run build`

### Auth/JWT (sem interacao)
- manter `.secrets/auth.json` (fora do git)
- gerar token via `/api/v1/auth/login`
- salvar `.secrets/chat_jwt.txt` (uma linha: `Bearer <token>`)

### E2E
- POST `/api/v1/chat/message` e validar evidence(job)
- UI: `/chat` -> abrir Job -> validar `/audit`

## 5) Plano de CI (GitHub Actions) - diagnostico e correcao
**Snapshot encontrado:**
- Python 3.12 (setup-python@v5)
- Node 20 (setup-node@v4)
- Steps: ruff, pyright (npx), pytest, npm ci/build

**Hipoteses comuns de falha:**
- mismatch de Node local (22) vs CI (20)
- dependencias do backend/pyright variando por versao
- falta de cache npm/pip
- docker/compose steps ausentes ou servicos nao sobem (db/redis)

**Acao recomendada (ordem):**
1) padronizar Node (ou CI->22 ou local->20) e travar via .nvmrc/volta/docs
2) adicionar cache (npm + pip)
3) garantir services (postgres/redis) e healthcheck antes do pytest
4) publicar logs do ultimo run e corrigir step exato

## 6) Riscos e Mitigacoes
- **CI vermelho**: bloquear merge -> mitigar com ajuste minimo de workflow + pin de versoes
- **DDL runtime jobs**: risco medio -> migrar para Alembic no inicio da S4
- **Segredos (auth/jwt)**: risco alto -> garantir `.secrets/` no .gitignore e nunca logar token
