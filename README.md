# Tribultz

Plataforma de compliance e simulação CBS/IBS para a reforma tributária brasileira (LC 214 + LC 227): validação fiscal em tempo real, reconciliação, trilha auditável e dashboard executivo.

## Stack

| Camada | Tecnologia |
|--------|------------|
| Frontend | Next.js 16, React 19, TypeScript 5, Tailwind CSS 3 |
| Backend | FastAPI, SQLAlchemy, Alembic, Python 3.12 |
| AI/Agents | CrewAI 1.10, LiteLLM (OpenRouter — Gemini 2.0 Flash / Qwen3 Coder / Claude 3.5 Sonnet) |
| Workers | Celery 5.4 + Redis 7 |
| Database | PostgreSQL 16 (multi-tenant, UUID PKs) |
| Storage | MinIO (S3-compatible) |
| Infra | Docker Compose |
| CI | GitHub Actions — backend-gates + frontend-build |

## Estrutura do projeto

```
frontend/            Next.js app (app router)
  src/app/           Páginas: dashboard, validate-xml, validate-batch, audit, chat,
                     closing, jobs, report, settings, login, register, exceptions
  src/lib/           Validação (xmlRules), export (CSV/PDF auditável, batch, zip), closing
  src/components/    UI: AppShell, Sidebar, EvidenceList, JsonViewer, Toast

backend/             FastAPI
  app/routers/       audit, auth, chat, health, jobs, tasks, validate, validation
  app/crews/         CrewAI chatops crew + LLM fallback chain
  app/tasks/         Celery tasks (validate, report, simulation, reconciliation)
  app/tools/         ERP connector, HubSpot, Postgres, S3, validation
  tests/             pytest

database/            DDL (schema.sql) — 9 tabelas multi-tenant + seed data
infra/               docker-compose.yml
docs/sprints/        Histórico de sprints e relatórios de entrega
```

## Quick start

### Infra (Docker)

```bash
docker compose -f infra/docker-compose.yml up -d
```

### Backend

```bash
cd backend
source .venv/Scripts/activate   # Windows
# source .venv/bin/activate     # Linux/Mac
python -m pytest tests/ -q
ruff check app/ tests/
uvicorn app.main:app --reload   # porta 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev    # porta 3000
npm test       # 41 testes
npm run build  # produção
```

## Portas

| Serviço | URL |
|---------|-----|
| Console (Frontend) | http://localhost:3000 |
| API (Backend) | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| MinIO | http://localhost:9000 |

## Fluxo de uso

1. **Login** — Demo (mock, sem backend) ou API (autenticação real)
2. **Registro** — `/register` com auto-login após cadastro
3. **Dashboard** — KPIs: jobs 24h, total validações, taxa conformidade, exceções abertas, total findings, FATAL count, top 3 regras violadas, trend 7 dias
4. **Validar XML** — Upload NFS-e/NF-e → validação CBS/IBS → download CSV/PDF auditável
5. **Lote** — Upload múltiplos XMLs → validação sequencial com progress bar → relatório consolidado CSV/PDF
6. **Chat** — Assistente fiscal com CrewAI (3 agentes: triage → operator → narrator)
7. **Jobs** — Histórico de execuções com export de evidências (.zip)
8. **Auditoria** — Trilha auditável com SHA-256 checksums
9. **Exceções** — Workflow OPEN → APPROVED/REJECTED com eventos no audit

## Regras de domínio

- **CBS**: Contribuição sobre Bens e Serviços (federal) — alíquota referência 0,10%
- **IBS**: Imposto sobre Bens e Serviços (estadual/municipal) — alíquota referência 0,90%
- **Base legal**: LC 214 (reforma tributária) + LC 227 (regulamentação)
- **10 regras determinísticas** com evidência auditável no formato Findings/Evidence v1.1
- Relatório auditável: NF | BASE ICMS | VALOR ICMS | IBS | CBS | CEST | CLASSTRIB

## Validação dual-stack

- **Frontend mock** (`xmlRules.ts`) — roda sem backend, Mock Mode ON por padrão
- **Backend API** (`/api/v1/validate/cbs-ibs`) — TaxEngine contra regras no PostgreSQL
- Cada regra produz Finding com severidade (FATAL/ALERT) e evidência mínima

## Auth e multi-tenancy

- JWT via `POST /api/v1/auth/login` — toda request envia `Authorization: Bearer <token>` + `X-Tenant-Id`
- Registro via `POST /api/v1/auth/register` com resolução de tenant por slug
- Endpoints são tenant-scoped (anti-IDOR)
- Console suporta toggle Mock/API mode

## CrewAI — LLM fallback chain

| Prioridade | Modelo | Tipo |
|------------|--------|------|
| 1 | Gemini 2.0 Flash | Free (OpenRouter) |
| 2 | Qwen3 Coder 480B | Free (OpenRouter) |
| 3 | Claude 3.5 Sonnet | Paid (fallback) |

Configuração via `OPENROUTER_API_KEY` no `.env`.

## CI Gates

```bash
# Frontend
cd frontend && npm test --silent && npm run build

# Backend
cd backend && source .venv/Scripts/activate && python -m pytest tests/ -q && ruff check app/ tests/
```

## Convenções

- **Commits**: Conventional Commits — `feat(s8):`, `fix(s8):`, `docs(s8):`
- **Branch**: uma branch por issue, PR único por issue
- **Lint**: ruff (backend), TypeScript strict (frontend)
