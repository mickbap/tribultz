# CLAUDE.md — Tribultz

Plataforma de validação fiscal para a reforma tributária brasileira (LC 214 + LC 227).
Motor determinístico que verifica notas fiscais contra regras CBS/IBS e gera evidências auditáveis.

## Stack

| Camada | Tecnologia |
|--------|------------|
| Frontend | Next.js 16, React 19, TypeScript 5, Tailwind CSS 3, tsx --test |
| Backend | FastAPI, SQLAlchemy, Alembic, Python 3.12 |
| AI/Agents | CrewAI 1.10 (ParseNFSeXMLTool, ValidateFiscalRulesTool), LiteLLM |
| Workers | Celery 5.4 + Redis 7 (task queue / beat scheduler) |
| Database | PostgreSQL 16 (multi-tenant, UUID PKs, tenant_id FK em todas as tabelas) |
| Storage | MinIO (S3-compatible) |
| Infra | Docker Compose (db, redis, minio, api, worker, beat) |
| CI | GitHub Actions — backend-gates + frontend-build |

## Estrutura do projeto

```
frontend/          Next.js app (app router)
  src/app/         Páginas: validate-xml, audit, chat, closing, dashboard, jobs, report, settings
  src/lib/         Lógica de validação (xmlRules), export (bundle, zip), closing (aggregate)
  src/components/  UI: AppShell, Sidebar, EvidenceList, JsonViewer, Toast

backend/           FastAPI
  app/routers/     audit, auth, chat, health, jobs, tasks, validate, validation
  app/crews/       CrewAI chatops crew + tools
  app/tasks/       Celery tasks (validate, report, simulation, reconciliation, hubspot)
  app/tools/       ERP connector, HubSpot, Postgres, S3, validation
  tests/           pytest

crews/             CrewAI crews (chatops, devops)
database/          DDL (schema.sql) — 9 tabelas multi-tenant + seed data
infra/             docker-compose.yml
tools/qa_gates/    run_gates.py — QA automation
docs/sprints/      Histórico de sprints e relatórios de entrega
```

## Convenções

- **Commits**: Conventional Commits — `feat(s8):`, `fix(s8):`, `docs(s8):`
- **Branch**: uma branch por issue, PR único por issue
- **Testes frontend**: `cd frontend && npm test --silent`
- **Testes backend**: `cd backend && source .venv/bin/activate && python -m pytest tests/ -q`
- **Lint backend**: `ruff check app/ tests/`
- **Build frontend**: `cd frontend && npm run build`
- **Type check backend**: `npx pyright@1.1.386`

## Gates (obrigatório antes de PR)

```bash
# Frontend
cd frontend && npm test --silent && npm run build

# Backend
cd backend && source .venv/bin/activate && python -m pytest tests/ -q && ruff check app/ tests/
```

## Regras de domínio

- **CBS**: Contribuição sobre Bens e Serviços (federal) — fase de teste 2026: **0,9%**; referência plena (regime cheio, ~2033): **8,8%**
- **IBS**: Imposto sobre Bens e Serviços (estadual/municipal) — fase de teste 2026: **0,1%**; referência plena (regime cheio, ~2033): **17,7%** (UF + Município)
- **Base legal**: LC 214 (reforma tributária) + LC 227 (regulamentação)
- **20 regras determinísticas** no engine (`frontend/src/lib/validation/xmlRules.ts`, fonte canônica `RULES_COUNT`; 22 ruleIds − 2 placeholders) com evidência auditável no formato Findings/Evidence v1.1
- **Vocabulário fiscal**: CEST, ClassTrib, IBS, CBS, Nota Nacional, ISS, ICMS, Split Payment, Cashback

## Validação

- Dual-stack: frontend mock (xmlRules.ts) + backend API (/validate/cbs-ibs)
- Cada regra produz Finding com severidade (ERROR/WARNING/INFO) e evidência mínima
- Relatório auditável: NF | BASE ICMS | VALOR ICMS | IBS | CBS | CEST | CLASSTRIB

## Dev servers

- Frontend: `cd frontend && npm run dev` → porta 3000
- Backend + infra: `docker compose -f infra/docker-compose.yml up -d` → porta 8000

## Deploy

- **Automático**: push em `main` afetando `backend/**` ou `infra/**` dispara `.github/workflows/deploy-prod.yml`, que roda `deploy.sh` na VM Magalu via SSH (rollback automático em falha)
- **Manual**: Actions → "Deploy Prod (Magalu)" → Run workflow (com flags `migrate` / `skip_pull`)
- **Frontend**: deploy via Vercel (não dispara este workflow)
- Secrets necessários: `MAGALU_SSH_KEY`, `MAGALU_SSH_HOST`, `MAGALU_SSH_USER`

## Superpowers skills disponíveis

| Skill | Uso |
|-------|-----|
| systematic-debugging | Diagnóstico de bugs — seguir antes de patches |
| test-driven-development | Features novas — escrever testes primeiro |
| verification-before-completion | Checklist antes de abrir PR |
| writing-plans | Planejamento de features complexas |
| executing-plans | Execução estruturada de planos |
| requesting-code-review | Pedir review de código |
| receiving-code-review | Processar feedback de review |
| subagent-driven-development | Tarefas paralelas com subagentes |
| using-git-worktrees | Trabalho isolado em worktrees |
| brainstorming | Exploração de soluções |
