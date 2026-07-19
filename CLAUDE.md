# CLAUDE.md — Tribultz

Plataforma de validação fiscal para a reforma tributária brasileira (LC 214 + LC 227).
Motor determinístico que verifica notas fiscais contra regras CBS/IBS e gera evidências auditáveis.

## Product First — governança da decisão de engenharia

A plataforma é considerada tecnicamente madura (governança arquitetural, auditoria
arquitetural, auditoria de dependências e ciclo de vida das Crews já institucionalizados —
ver `knowledge/decisions/` no Brain). O roadmap de produto, não a oportunidade técnica
percebida, é a força organizadora do trabalho. Fonte de verdade completa:
[ADR-0014](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/decisions/2026-07-18-product-first-governanca-de-decisao.md)
no Brain — o que segue é o resumo operacional.

- **Product First**: ao propor trabalho novo, priorize o que aumenta valor entregue ao
  usuário. Não proponha espontaneamente refatoração, upgrade ou melhoria horizontal só
  porque é tecnicamente possível.
- **Governança antes da implementação**: antes de sugerir mudança estrutural, verifique
  se já existe RFC, ADR ou Issue priorizada. Na ausência desses artefatos, não inicie
  implementação — proponha o artefato que falta primeiro.
- **Arquitetura como meio**: arquitetura serve ao produto. Nunca trate evolução
  arquitetural como objetivo em si.
- **Infraestrutura em modo de manutenção**: infra, observabilidade, CI/CD, dependências e
  governança são capacidades permanentes — evoluem só por incidente, risco, requisito
  explícito ou planejamento aprovado, nunca por iniciativa espontânea.
- **Roadmap é a fonte da verdade**: `knowledge/product/roadmap.md` (Brain) governa o
  trabalho. Não reordene prioridades por interesse técnico.

**Hierarquia de decisão** ao iniciar qualquer ciclo: Issue P0 aberta → executar. Issue P1
aberta → executar. Incidente de produção → tratar. Requisito legal/regulatório → tratar.
Vulnerabilidade crítica explorável → tratar. Só então: melhoria arquitetural, refatoração,
upgrade, otimização — e mesmo essa entra como Issue P2/P3 normal pela
[matriz de priorização](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/product/backlog-priority-matrix.md),
nunca como iniciativa espontânea.

**Antes de implementar, confirme** (Definition of Ready): a Issue pertence ao roadmap
vigente; a prioridade veio da matriz, não de estimativa ad hoc; não há P0 de maior valor
aguardando; a implementação contribui a um objetivo de negócio do horizonte correspondente
ou atende a um risco explicitamente reconhecido. Justifique a exceção ao roadmap — não a
execução dele.

## Stack

| Camada | Tecnologia |
|--------|------------|
| Frontend | Next.js 16, React 19, TypeScript 5, Tailwind CSS 3, tsx --test |
| Backend | FastAPI, SQLAlchemy, Alembic, Python 3.12 |
| AI/Agents | CrewAI 1.10 (CRM Engagement em produção; Security Crew interna; NFe Validation dormante — ver `knowledge/engineering/crews.md` no Brain), LiteLLM |
| Workers | Celery 5.6 + Redis 7 (task queue / beat scheduler) |
| Database | PostgreSQL 16 (multi-tenant, UUID PKs, tenant_id FK em todas as tabelas) |
| Storage | MinIO (S3-compatible) |
| Infra | Docker Compose (db, redis, minio, api, worker, beat) |
| CI/Automação | GitHub Actions — backend-gates, frontend-build, deploy-prod, monitor (uptime → alerta Resend), classtrib-sync (re-sync diário cClassTrib SVRS → PR revisado), soro-blog-sync (RSS Soro → PR revisado) |

## Estrutura do projeto

```
frontend/          Next.js app (app router)
  src/app/         Páginas: validate-xml, audit, closing, dashboard, jobs, report, settings,
                   admin (painel superadmin: visão geral, tenants, usuários, uso, saúde, audit log), blog
  src/lib/         Lógica de validação (xmlRules), export (bundle, zip), closing (aggregate),
                   contentLint (corretor fiscal do blog), soroSync (Soro RSS→MDX), useAdminData
  src/components/  UI: AppShell, Sidebar, EvidenceList, JsonViewer, Toast

backend/           FastAPI
  app/routers/     28 routers (auditado 16/07/2026) — admin, audit, auth, billing, calculadora,
                   classtrib, compliance, credits, documents, exceptions, feedback,
                   founding_partners, health, jobs, lgpd, ncm_suggest, news, public, public_api,
                   reports, simulator, sped, split_payment, support, tasks, validate,
                   validate_xml, validation. Chat foi descontinuado como produto (mai/2026) e o
                   código remanescente removido (ADR-0012, ver `knowledge/decisions/` no Brain).
  app/crews/       CrewAI crews — crm_engagement_crew (Produção), security_crew (Produção
                   Interna), nfe_validation_crew (Dormante). Classificação oficial e políticas em
                   `knowledge/engineering/crews.md` no Brain.
  app/tasks/       10 tasks Celery (validate, report, simulation, reconciliation, hubspot,
                   security_audit — órfã, sem beat/autodiscover, ver runbook —, billing, sped,
                   compliance, crm)
  app/tools/       ERP connector, HubSpot, Postgres, S3, validation
  tests/           pytest

crews/             Configs YAML (agents/tasks) das crews em app/crews/ — nfe_validation, security
database/          README — schema é 100% Alembic (backend/app/alembic); schema.sql aposentado (#409)
infra/             docker-compose.yml
tools/qa_gates/    run_gates.py — QA automation
tools/architecture_audit.py   Auditoria arquitetural (ADR-0013) — Crews sem classificação,
                               tasks Celery não registradas, tools órfãs, routers vs. CLAUDE.md,
                               sincronia com o Brain. Achados com severidade (Crítico/Alto/Médio/
                               Baixo — política em knowledge/process/architecture-audit-policy.md
                               no Brain). Roda no CI (job backend-gates, após Pytest) em modo
                               informativo — não bloqueia merge. Local: `cd backend && source
                               .venv/bin/activate && python ../tools/architecture_audit.py`
docs/sprints/      Histórico de sprints e relatórios de entrega
docs/infra/operations_runbook.md   Arquitetura, fluxo de deploy/rollback, recuperação de
                                    ambiente, checklist de auditoria operacional
```

## Convenções

- **Commits**: Conventional Commits — `feat(s8):`, `fix(s8):`, `docs(s8):`
- **Branch**: uma branch por issue, PR único por issue
- **Testes frontend**: `cd frontend && npm test --silent`
- **Testes backend**: `cd backend && source .venv/bin/activate && python -m pytest tests/ -q`
- **Lint backend**: `ruff check app/ tests/`
- **Build frontend**: `cd frontend && npm run build`
- **Type check backend**: `npx pyright@1.1.411`

## Gates (obrigatório antes de PR)

```bash
# Frontend
cd frontend && npm test --silent && npm run build

# Backend — pré-requisito: infra local no ar (ver "Dev servers"). Testes que
# disparam tasks Celery (ex.: tests/test_billing_webhook.py) precisam de um
# Redis real em localhost:6379; sem ele falham com ConnectionRefusedError.
cd backend && source .venv/bin/activate && python -m pytest tests/ -q && ruff check app/ tests/
```

## Contexto durável — leia antes de agir

- `docs/context/` — conhecimento que vale para qualquer máquina: vocabulário fiscal oficial, base legal, regras da contabilidade, referências de APIs, convenções e decisões de produto. **Fonte de verdade**; a memória local do agente é só cache. Nunca colocar credencial lá.
- `docs/infra/secrets_inventory.md` — onde os segredos vivem, como validar sem expor valores, onboarding de máquina nova. Fonte de verdade dos segredos: `/opt/tribultz/.env` na VM.
- `tools/check_access.sh` — valida SSH, mgc, gh, Vercel, drift do `.env.prod` e saúde da produção.

## Regras de domínio

- **CBS**: Contribuição sobre Bens e Serviços (federal) — fase de teste 2026: **0,9%**; referência plena (regime cheio, ~2033): **8,8%**
- **IBS**: Imposto sobre Bens e Serviços (estadual/municipal) — fase de teste 2026: **0,1%**; referência plena (regime cheio, ~2033): **17,7%** (UF + Município)
- **Base legal**: LC 214 (reforma tributária) + LC 227 (regulamentação)
- **33 regras determinísticas** no engine mock (`frontend/src/lib/validation/xmlRules.ts`, fonte canônica `RULES_COUNT`; 35 ruleIds − 2 placeholders), cobrindo NT 2025.002-RTC v1.40 + NT 2026.002 v1.00 (NF-e/NFC-e — DANFE Simplificado Tipo 2/tpImp=6, regra `DANFE_SIMPLIFICADO_RESTRICAO`, Rejeições 706/707/708/715, diff estrutural em `docs/nt2026002_nt2026003_diff.md`, #405) **e** NT 007/2026 SE/CGNFS-e (NFS-e — `INDZFMALC_CBS_ZERO`, `PIS_COFINS_DEVIDO_NEGATIVO`, #406) + **regras de enrichment backend-only** que dependem da tabela SVRS (cClassTrib × CST = **Rejeição 1024**, alíquota zero/absoluta, cClassTrib × modelo de DFe, cCredPres, subgrupos do regime monofásico de combustíveis — grupo UB84/gIBSCBSMono, NT 2025.002 v1.50, regra `MONOFASICO_GRUPO_UB` — cobertura parcial: checagem estrutural de presença, não valida os valores de ad rem, #404). Catálogo de rejeições da NT v1.40 coberto, citando códigos oficiais (1024, 1099, 1106, 1110, 1118, 1119, 1192, 1218, C22-20…). Evidência auditável no formato Findings/Evidence v1.1
- **Tabela cClassTrib oficial** (`backend/app/data/classtrib.json`, fonte SVRS pública): 164 códigos, re-sincronizada diariamente via workflow `classtrib-sync` (cresce com frequência — sem re-sync, o motor decai). `CLASSTRIB_COUNT` em `rulesMeta.ts`.
- **Vocabulário fiscal**: CEST, ClassTrib, IBS, CBS, Nota Nacional, ISS, ICMS, Split Payment, Cashback

## Validação

- Dual-stack: frontend mock (xmlRules.ts) + backend API (/validate/cbs-ibs)
- Cada regra produz Finding com severidade (ERROR/WARNING/INFO) e evidência mínima
- Relatório auditável: NF | BASE ICMS | VALOR ICMS | IBS | CBS | CEST | CLASSTRIB

## Dev servers

- Frontend: `cd frontend && npm run dev` → porta 3000
- Backend + infra: `docker compose -f infra/docker-compose.yml up -d --build` → porta 8000
  - `--build` é necessário sempre que o código do backend ou uma migration Alembic mudar — o Compose reutiliza a imagem em cache e não rebuilda sozinho. Sem isso, o serviço one-shot `migrate` pode falhar com `Can't locate revision identified by '<rev>'` (imagem desatualizada não conhece a migration nova), e `api`/`worker`/`beat` ficam parados porque dependem de `migrate` completar com sucesso.

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
