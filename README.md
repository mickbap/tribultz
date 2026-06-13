# Tribultz — Inteligência Fiscal para a Reforma Tributária

> Motor determinístico de validação CBS/IBS · Multi-tenant SaaS · LC 214 + LC 227

[![CI Backend](https://github.com/mickbap/tribultz/actions/workflows/ci.yml/badge.svg)](https://github.com/mickbap/tribultz/actions/workflows/ci.yml)
[![Testes](https://img.shields.io/badge/testes-469%20passing-brightgreen)](#ci--cd)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org)
[![Next.js](https://img.shields.io/badge/next.js-16-black)](https://nextjs.org)
[![Licença](https://img.shields.io/badge/licença-proprietária-red)](#licença)

---

## Sumário Executivo

A reforma tributária brasileira (Lei Complementar 214/2026 e LC 227) unifica PIS, COFINS e IPI em um único tributo federal — a **CBS** — e o ICMS e ISS em um único tributo subnacional — o **IBS**. A transição começa em 2026, e cada nota fiscal emitida precisará conter o grupo `<IBSCBS>` corretamente calculado, com CST, alíquotas e créditos dentro das regras da NT 2025.002-RTC.

**Tribultz é a plataforma que valida, calcula e audita essa transição.**

O motor determinístico aplica 14 regras de conformidade contra XML de NF-e, NFC-e e NFS-e, produzindo evidências auditáveis no formato _Findings/Evidence v1.1_. O operador fiscal recebe em segundos um diagnóstico completo: o que está errado, qual regra foi violada e qual o impacto financeiro — sem depender de interpretação humana.

**Por que agora?** O prazo regulatório não move. Empresas que não adequarem seus ERPs antes de janeiro de 2026 emitirão notas inválidas, terão créditos glosados e enfrentarão multas retroativas. A janela de preparação é a oportunidade de mercado.

**Diferenciais:**
- Único validador que gera o snippet XML `<IBSCBS>` pronto para o ERP
- **Simulador de Impacto** — compara carga tributária atual (ICMS+PIS/COFINS+ISS) vs CBS+IBS por regime e setor
- **Modo Período Educativo LC 227** — downgrade automático de obrigações acessórias em 2026 (nenhum concorrente faz isso)
- **dPrevEntrega** — único sistema que detecta divergência de competência entre contabilização e apuração IBS
- Calculadora CBS/IBS pública como primeiro ponto de conversão freemium
- Diagnóstico XML gratuito (3 findings) — captura o lead no momento da dor
- Arquitetura multi-tenant pronta para contadores que gerenciam múltiplos CNPJs
- Infraestrutura 100% nacional (Magalu Cloud) — soberania de dados, sem variação cambial

---

## Funcionalidades

### Freemium (sem cadastro)

| Funcionalidade | Endpoint | Limite |
|---|---|---|
| Calculadora CBS/IBS | `GET /calculadora` | 20 cálculos/dia por IP |
| **Simulador de Impacto** | `POST /api/v1/public/simulator/regime` | 30 req/min por IP |
| Diagnóstico XML | `GET /diagnostico` | 3 findings por arquivo |
| Validação pública | `POST /api/v1/public/validate-xml` | 20 req/dia por IP |

### Plataforma (conta ativa)

| Funcionalidade | Descrição |
|---|---|
| **Validação XML** | Upload de NF-e, NFC-e e NFS-e; 22 regras NT 2025.002-RTC v1.40; resultado em <2s |
| **Modo Período Educativo** | Toggle LC 227/2026 art. 348: obrigações acessórias viram WARNING em vez de FATAL com badge legal |
| **dPrevEntrega (NT V1.36)** | 3 regras: Rejeição 1157 preventiva, divergência competência CBS/IBS, CIF sem data entrega |
| **Validação em lote** | Fila Celery; N arquivos em paralelo; relatório consolidado |
| **Chat AI Fiscal** | CrewAI (Triager → Operator → Narrator); responde perguntas sobre conformidade com citação de regra |
| **Relatório auditável** | PDF + Markdown; campos NF · BASE ICMS · VALOR ICMS · IBS · CBS · CEST · CLASSTRIB |
| **Exceções** | Workflow OPEN → APPROVED → REJECTED com justificativa e trilha auditável |
| **Créditos tributários** | Rastreio de créditos CBS/IBS por CNPJ/período |
| **Encerramento de período** | Agregação de obrigações; exportação ZIP com evidências assinadas |
| **Dashboard** | KPIs em tempo real: total validado, taxa de erro, créditos acumulados |
| **Billing Asaas** | Assinatura recorrente (PIX + cartão); 5 planos; trial 3 dias; notificações D-3/D-1/expirado; webhooks idempotentes |
| **CRM automatizado** | HubSpot lifecycle gerenciado por Crew: contato/deal sync + emails personalizados de dunning e win-back via CrewAI |
| **Monitoring** | Health check a cada 5 min (GitHub Actions); alerta por email se `/health/deep` degradar |
| **LGPD** | Export de dados pessoais + solicitação de exclusão (`/lgpd/data`, `/lgpd/delete`) |

---

## Planos

| Plano | Preço/mês | Validações | Mensagens AI | Usuários | Multi-CNPJ |
|---|---|---|---|---|---|
| **Trial** | Grátis | 5 | 10 | 1 | — |
| **Starter** | R$ 49,90 | 100 | 50 | 1 | — |
| **Profissional** | R$ 149,00 | 1.000 | 200 | 3 | — |
| **Empresarial** | R$ 249,00 | 5.000 | 500 | 10 | ✅ |
| **Contador** | R$ 349,00 | Ilimitado | Ilimitado | Ilimitado | ✅ |

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENTE / BROWSER                    │
│         tribultz.com.br  ·  Next.js 16 + React 19       │
│    29 páginas · Tailwind CSS · TypeScript 5 · tsx test  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS
                       ▼
┌─────────────────────────────────────────────────────────┐
│               CLOUDFLARE (CDN + Turnstile)              │
│          Vercel (deploy frontend)                        │
└──────────────────────┬──────────────────────────────────┘
                       │ api.tribultz.com.br
                       ▼
┌─────────────────────────────────────────────────────────┐
│                NGINX (reverse proxy)                    │
│      TLS · security headers · rate limit 30r/min        │
└──────────────────────┬──────────────────────────────────┘
                       │ 127.0.0.1:8000
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   FASTAPI (api)                         │
│   16 routers · JWT auth · multi-tenant · Pydantic v2    │
│   CrewAI crews · LiteLLM · OpenRouter                   │
└──────┬──────────────────────────┬───────────────────────┘
       │ SQLAlchemy                │ Celery tasks
       ▼                          ▼
┌─────────────┐         ┌─────────────────────────┐
│ PostgreSQL  │         │   CELERY (worker + beat) │
│  16 (DBaaS) │         │  10 tasks · concurrency=2│
│  16 tabelas │         │   Redis broker           │
│  multi-tenant│        └──────────┬──────────────┘
└─────────────┘                    │
                          ┌────────┴────────┐
                          │                 │
                    ┌──────────┐    ┌──────────────┐
                    │  REDIS   │    │ MAGALU S3     │
                    │  (cache  │    │ (documentos,  │
                    │  + broker│    │  PDFs, exports)│
                    └──────────┘    └──────────────┘

┌─────────────────────────────────────────────────────────┐
│                  APIS EXTERNAS                          │
│  Asaas (pagamentos)  ·  ClassTrib SVRS  ·  CNPJ.ws     │
│  OpenRouter (LLM)   ·  Cloudflare Turnstile             │
│  HubSpot CRM (ativo) · HubSpot Tracking (portal 49735644)│
└─────────────────────────────────────────────────────────┘
```

### Multi-tenant

Todas as 15 tabelas possuem coluna `tenant_id UUID NOT NULL`. Nenhuma query cruza tenants — o `current_user.tenant_id` extraído do JWT é o único critério de escopo. Índices compostos `(tenant_id, X)` em todas as tabelas quentes.

### Motor de validação (dual-stack)

| Camada | Implementação | Quando usar |
|---|---|---|
| Frontend mock | `src/lib/validation/xmlRules.ts` | Preview instantâneo, offline |
| Backend API | `POST /api/v1/validate/cbs-ibs` | Resultado oficial, persistido |

As duas implementações são determinísticas e produzem o mesmo resultado para o mesmo input — garantido pelo conjunto de testes compartilhado.

---

## Stack Tecnológico

| Camada | Tecnologia | Versão |
|---|---|---|
| Frontend | Next.js | 16.1.6 |
| UI | React + TypeScript | 19.2.3 / 5 |
| Estilos | Tailwind CSS | 3.4 |
| Testes frontend | tsx | 4.20 |
| Backend | FastAPI + Python | 3.12 |
| ORM | SQLAlchemy + Alembic | — |
| Schemas | Pydantic V2 | — |
| AI/Agents | CrewAI | 1.10 |
| LLM Gateway | LiteLLM + OpenRouter | — |
| Task queue | Celery | 5.4 |
| Broker/Cache | Redis | 7-alpine |
| Banco de dados | PostgreSQL | 16 |
| Storage | S3-compatible (Magalu) | — |
| Pagamentos | Asaas | — |
| CAPTCHA | Cloudflare Turnstile | — |
| Email | SMTP (Gmail App Password) | — |
| Infra dev | Docker Compose | — |
| Infra prod | Magalu Cloud VM + DBaaS | — |
| Frontend deploy | Vercel | — |
| CI/CD | GitHub Actions | — |
| Lint/Type | Ruff + Pyright | — |

---

## API Reference

### Autenticação

| Método | Rota | Descrição | Auth | Rate limit |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Registro (com Turnstile) | — | 3/60s |
| `POST` | `/api/v1/auth/login` | Login → JWT | — | 5/60s |
| `POST` | `/api/v1/auth/logout` | Logout | JWT | — |
| `POST` | `/api/v1/auth/verify-email` | Confirmar e-mail | — | — |
| `POST` | `/api/v1/auth/forgot-password` | Solicitar reset | — | — |
| `POST` | `/api/v1/auth/reset-password` | Aplicar nova senha | — | — |

### Validação

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| `POST` | `/api/v1/validate/cbs-ibs` | Validar NF com cálculo CBS/IBS | JWT |
| `POST` | `/api/v1/validate-xml` | Validar XML (NF-e, NFC-e, NFS-e) | JWT |
| `POST` | `/api/v1/public/validate-xml` | Validar XML (sem auth, 3 findings máx) | — |

### Calculadora

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| `POST` | `/api/v1/public/calculadora/regime-geral` | Calcular CBS/IBS por NCM/UF | — |
| `POST` | `/api/v1/calculadora/regime-geral` | Calcular com alíquotas do tenant | JWT |

### Simulador de Impacto

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| `POST` | `/api/v1/public/simulator/regime` | Simular impacto CBS/IBS por regime e setor | — |
| `GET` | `/api/v1/calculadora/uf-rates` | Alíquotas por estado | JWT |

### Jobs & Tasks

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| `POST` | `/api/v1/jobs` | Criar job de validação/relatório | JWT |
| `GET` | `/api/v1/jobs/{id}` | Status + findings do job | JWT |
| `PATCH` | `/api/v1/jobs/{id}` | Atualizar status | JWT |
| `POST` | `/api/v1/tasks/{id}/trigger` | Disparar task manualmente | JWT |

### Documentos

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| `POST` | `/api/v1/documents/upload-url` | Presigned PUT (5min TTL) | JWT |
| `POST` | `/api/v1/documents/confirm` | Confirmar upload + indexar XML | JWT |
| `GET` | `/api/v1/documents` | Listar documentos | JWT |
| `GET` | `/api/v1/documents/{id}/download` | Presigned GET (15min TTL) | JWT |

### Relatórios & Auditoria

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| `POST` | `/api/v1/reports/validation-pdf` | Gerar PDF de validação | JWT |
| `POST` | `/api/v1/reports/batch-pdf` | PDF em lote | JWT |
| `GET` | `/api/v1/audit` | Log de auditoria (filtros) | JWT |
| `POST` | `/api/v1/audit/log` | Registrar evento | JWT |

### Chat AI

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| `POST` | `/api/v1/chat/message` | Pergunta fiscal → CrewAI | JWT |

### Billing

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| `GET` | `/api/v1/billing/plans` | Listar planos | — |
| `POST` | `/api/v1/billing/subscribe` | Assinar/atualizar plano | JWT |
| `POST` | `/api/v1/billing/webhooks/asaas` | Webhook Asaas | HMAC |

### LGPD & Outros

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| `GET` | `/api/v1/lgpd/data` | Export de dados pessoais | JWT |
| `POST` | `/api/v1/lgpd/delete` | Solicitar exclusão | JWT |
| `POST` | `/api/v1/feedback` | Enviar feedback | JWT |
| `GET` | `/api/v1/health` | Health check | — |

> Documentação interativa: `http://localhost:8000/docs` (Swagger UI)

---

## Frontend — Páginas

| Rota | Acesso | Descrição |
|---|---|---|
| `/` | Pública | Landing page |
| `/calculadora` | Pública | Calculadora CBS/IBS com snippet XML |
| `/simulador` | Pública | Simulador de Impacto por Regime Tributário |
| `/diagnostico` | Pública | Diagnóstico fiscal gratuito (3 findings) |
| `/pricing` | Pública | Planos e preços |
| `/register` | Pública | Cadastro (Turnstile + e-mail verification) |
| `/login` | Pública | Login (modo demo ou API) |
| `/dashboard` | Auth | KPIs, jobs recentes, alertas |
| `/validate-xml` | Auth | Upload e validação de XML |
| `/validate-batch` | Auth | Validação em lote |
| `/chat` | Auth | Chat AI fiscal (CrewAI) |
| `/jobs` | Auth | Fila de jobs e status |
| `/jobs/[id]` | Auth | Findings, evidências, timeline AI |
| `/exceptions` | Auth | Workflow de exceções |
| `/audit` | Auth | Log de auditoria completo |
| `/closing` | Auth | Encerramento de período |
| `/billing` | Auth | Plano ativo e histórico |
| `/settings` | Auth | Tenant, token API, LGPD |
| `/cerebro` | Auth | AI insights (Cérebro) |
| `/changelog` | Auth | Histórico de versões |
| `/feedback` | Auth | Enviar feedback |
| `/privacy` | Pública | Política de privacidade |
| `/terms` | Pública | Termos de serviço |

---

## Banco de Dados

```
tenants ──┬── users ──── user_tenants
          ├── companies ─────────┬── invoices ── invoice_items
          ├── tax_rules          └── tax_credits
          ├── ncm_codes
          ├── plans ──── subscriptions ── payments
          ├── usage_tracking
          ├── audit_log
          └── feedback
```

| Tabela | Propósito |
|---|---|
| `tenants` | Entidade raiz — isolamento de dados |
| `users` | Autenticação · CNPJ · role · email_verified |
| `user_tenants` | Acesso multi-tenant (contador → N empresas) |
| `companies` | CNPJs dos contribuintes |
| `tax_rules` | Alíquotas CBS/IBS por período e tributação |
| `ncm_codes` | Nomenclatura Comum do Mercosul + alíquotas |
| `invoices` | NF-e, NFC-e, NFS-e indexadas |
| `invoice_items` | Itens com cálculo CBS/IBS por linha |
| `tax_credits` | Créditos acumulados por CNPJ |
| `plans` / `subscriptions` / `payments` | Billing completo via Asaas |
| `usage_tracking` | Contador mensal por tenant |
| `audit_log` | JSONB imutável + checksum SHA-256 |
| `feedback` | Feedback in-app por usuário |

---

## Regras de Validação (NT 2025.002-RTC v1.40)

| # | Regra | Severidade | Descrição |
|---|---|---|---|
| 1 | `CST_3_DIGITS` | FATAL | CST deve ter exatamente 3 dígitos |
| 2 | `CCLASSTRIB_6_DIGITS` | FATAL | cClassTrib deve ter 6 dígitos |
| 3 | `SERVICE_CODE_6_DIGITS` | FATAL | Código de serviço deve ter 6 dígitos |
| 4 | `XML_PARSE` | FATAL | XML deve ser válido e parseable |
| 5 | `NCM_PLACEHOLDER` | ALERT | NCM não pode ser todos zeros |
| 6 | `IBSCBS_MISSING` | FATAL | Grupo `<IBSCBS>` obrigatório para CSTs 000-550 |
| 7 | `IBSCBS_CALC` | FATAL | Cálculo CBS/IBS deve conferir (tolerância ±R$0,01) |
| 8 | `CEST_MISSING` | ALERT | CEST obrigatório apenas para produtos com substituição tributária (ST) |
| 9 | `CEST_FORMAT` | FATAL | CEST deve ter 7 dígitos no formato correto |
| 10 | `LAYOUT_PORTAL` | FATAL | Estrutura do XML deve seguir o layout da NT |
| 11–14 | Regras S11–S13 | WARNING | Validações complementares de alíquotas e créditos |
| 15 | `NCM_FORMAT` / `NCM_VALID` | FATAL | NCM deve ter 8 dígitos e ser válido na TIPI |
| 16 | `CLASSTRIB_VALID` | FATAL/ALERT | cClassTrib deve existir na tabela SVRS |
| 17 | `CNPJ_ACTIVE` | FATAL | CNPJ emitente deve estar ativo na Receita Federal |
| 18 | `DPREV_ENTREGA_FRETE` | **FATAL** | dPrevEntrega inválido para modFrete FOB/Sem Frete — Rejeição 1157 |
| 19 | `DPREV_ENTREGA_COMPETENCIA` | **ALERT** | dPrevEntrega em mês diferente de dhEmi — divergência contabilização × apuração IBS |
| 20 | `DPREV_ENTREGA_CIF_AUSENTE` | **ALERT** | Operação CIF sem dPrevEntrega — risco de IBS em período incorreto |

**Modo Período Educativo (LC 227/2026 art. 348):** quando ativo, as regras de obrigação acessória (8 regras) são downgraded de FATAL para WARNING com badge ⚖️ e nota dos 60 dias para sanar sem multa.

**CSTs suportados:** 000 · 001 · 002 · 070 · 200 · 410 · 510 · 515 · 550 · 620 · 800 · 810 · 811 · 830

---

## CrewAI — Agentes

### ChatOps Crew (backend)

```
Triager → Operator → Narrator
```

| Agente | Papel |
|---|---|
| `triager` | Classifica a pergunta; decide se aciona validação ou consulta |
| `operator` | Executa tools: GetJobStatus, TriggerTaskA |
| `narrator` | Formata resposta em Markdown com citação de regra e evidência |

Fallback determinístico: se o LLM falhar, retorna findings da validação diretamente.

### CRM Engagement Crew (backend)

```
CRM Analyst → Email Copywriter → Executor
```

| Agente | Papel |
|---|---|
| `CRM Analyst` | Lê contexto do cliente via DB (plan, status, usage, dias) e avalia risco de churn |
| `Email Copywriter` | Escreve email personalizado PT-BR com urgência CBS/IBS (dunning ou win-back) |
| `Executor` | Envia email via SMTP e loga nota no HubSpot (`send_email` + `hubspot_log_note`) |

Acionado por: `PAYMENT_OVERDUE` e `SUBSCRIPTION_DELETED`. Fallback para template estático se todos os 6 tiers LLM esgotarem. Camada determinística (`crm.sync`) cuida do contact/deal sync separadamente — sem LLM.

Tarefas Celery relacionadas:
- `crm.sync` — determinístico, mapeia lifecycle event → HubSpot deal stage
- `crm.engagement` — LLM crew para dunning/win-back
- `crm.audit` — daily beat 09:00, reconcilia subscriptions com updated_at < 24h

### NF-e Validation Crew (backend)

```
nfe_parser → ibscbs_validator → nfe_reporter
```

### DevOps Crew (standalone)

Auditoria contínua da stack de produção com 4 agentes e 9 tasks cobrindo tenant isolation, segurança de containers (CIS Docker Benchmark), hardening de VM, higiene de secrets e pipeline de deploy.

---

## Infraestrutura de Produção

### Stack Magalu Cloud

```
VM (Ubuntu 24.04)
├── Nginx (443/80) — TLS certbot + security headers
├── Docker Compose
│   ├── api      (FastAPI · 127.0.0.1:8000 · 1GB RAM)
│   ├── worker   (Celery · concurrency=2 · 768MB RAM)
│   ├── beat     (Celery scheduler · 6 schedules · 256MB RAM)
│   └── redis    (broker/cache · password · 256MB RAM)
├── UFW (22/80/443 apenas)
└── fail2ban (SSH + nginx)

Magalu DBaaS → PostgreSQL 16 (externo, VPC privada)
Magalu Object Storage → S3-compatible (br-se1)
Vercel → Frontend Next.js
```

### Deploy

**Auto-deploy (padrão)**: todo push em `main` que toque `backend/**` ou `infra/**` dispara o workflow [`deploy-prod.yml`](.github/workflows/deploy-prod.yml), que conecta na VM via SSH e roda `deploy.sh`. Mudanças só-frontend não disparam (frontend é Vercel).

Disparo manual (com flags) via Actions → "Deploy Prod (Magalu)" → Run workflow (`migrate` / `skip_pull` opcionais).

**Secrets necessários** (Settings → Secrets and variables → Actions):

| Secret | Valor |
|---|---|
| `MAGALU_SSH_KEY` | Chave privada ed25519 (`tribultz-infra`) — conteúdo completo do arquivo |
| `MAGALU_SSH_HOST` | `201.54.20.18` |
| `MAGALU_SSH_USER` | `ubuntu` |

**Execução manual na VM** (fallback / debug):

```bash
# Bootstrap inicial (uma vez, na VM)
sudo bash infra/scripts/magalu-init.sh

# Deploy contínuo
bash infra/scripts/deploy.sh

# Com migração de banco
bash infra/scripts/deploy.sh --migrate

# Apenas rebuild, sem git pull
bash infra/scripts/deploy.sh --skip-pull
```

O `deploy.sh` executa um rolling deploy sequencial com rollback automático:

1. Salva snapshot `:rollback` das imagens antes do build
2. Build das imagens Docker
3. Reinicia `api` → aguarda health check (`/health` 200)
4. Reinicia `worker` → verifica estado `running`
5. Reinicia `beat`
6. Em caso de falha: restaura `:rollback` como `:latest` e reinicia

---

## Segurança & SecDevOps

| Controle | Implementação |
|---|---|
| Monitoramento | GitHub Actions a cada 5 min · alerta email se `/health/deep` retornar status=error ou HTTP ≥ 400 |
| Autenticação | JWT HS256 · email verification · password reset |
| Multi-tenant | `tenant_id` em todas as queries · extraído do JWT |
| Rate limiting | Por IP em todos os endpoints públicos |
| CAPTCHA | Cloudflare Turnstile no registro |
| SSH | `PasswordAuthentication no` · `PermitRootLogin no` · MaxAuthTries 3 |
| Brute force | fail2ban (5 tentativas/10min → ban 1h) |
| Firewall | UFW default-deny · apenas 22/80/443 |
| TLS | certbot auto-renovação · HSTS |
| Nginx | `server_tokens off` · X-Frame-Options · X-Content-Type-Options · Referrer-Policy · Permissions-Policy · limit_req |
| Containers | `restart: unless-stopped` · resource limits · log rotation · rede interna |
| Secrets | `.env` excluído do git · `chmod 600` na VM · sem override de variáveis no compose |
| Rollback | Snapshot de imagem antes de cada build |
| Auditoria | Log JSONB imutável + checksum SHA-256 por evento |
| LGPD | Export de dados + exclusão sob demanda |

A DevOps Crew audita automaticamente todos esses controles contra CIS Ubuntu Benchmark, CIS Docker Benchmark e OWASP Secure Headers Project.

---

## CI/CD

```
Push / PR
    │
    ├── Backend Job
    │       ├── ruff check app/ tests/
    │       ├── pyright (type check)
    │       ├── alembic upgrade head
    │       ├── pytest tests/ -q  (469 testes)
    │       ├── crewai import sanity
    │       └── qa_gates/run_gates.py → artifact: qa_gates_report.md
    │
    └── Frontend Job
            ├── npm ci
            └── npm run build

Merge em main
    │
    ├── deploy-prod.yml → rolling deploy na VM Magalu (apenas backend/**)
    ├── publish-news.yml → POST /api/v1/news (feat/fix/security commits)
    └── monitor.yml (cron 5min) → GET /health/deep → alerta email se degradar
```

**Gates obrigatórios antes de PR:**

```bash
# Backend
cd backend && source .venv/Scripts/activate
python -m pytest tests/ -q && ruff check app/ tests/

# Frontend
cd frontend && npm test --silent && npm run build
```

---

## Desenvolvimento Local

### Pré-requisitos

- Docker + Docker Compose
- Node.js 20+
- Python 3.12+

### Setup

```bash
# 1. Clonar
git clone https://github.com/mickbap/tribultz.git
cd tribultz

# 2. Configurar variáveis de ambiente
cp backend/.env.example backend/.env
# Editar: JWT_SECRET, SMTP_*, ASAAS_API_KEY, OPENROUTER_API_KEY

# 3. Subir infraestrutura
docker compose -f infra/docker-compose.yml up -d

# 4. Frontend (modo dev)
cd frontend && npm install && npm run dev
# → http://localhost:3000

# 5. API docs
# → http://localhost:8000/docs
```

### Variáveis obrigatórias

| Variável | Descrição |
|---|---|
| `JWT_SECRET` | `openssl rand -hex 32` |
| `DATABASE_URL` | `postgresql+psycopg2://tribultz:pass@localhost:5432/tribultz` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `OPENROUTER_API_KEY` | Chave OpenRouter (LLM gateway) |
| `ASAAS_API_KEY` | Chave Asaas (pagamentos) |
| `SMTP_USER` / `SMTP_PASSWORD` | Gmail App Password |
| `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Object Storage credentials |
| `HUBSPOT_PRIVATE_APP_TOKEN` | HubSpot Private App token (opcional; `HUBSPOT_ENABLED=false` por padrão) |

---

## Roadmap

### Entregue

| Sprint | Funcionalidade |
|---|---|
| S1 | Backend FastAPI · PostgreSQL · Redis · MinIO · Celery · Docker Compose |
| S2–S3 | Frontend Next.js · Dashboard · Chat · Jobs · Audit · Settings |
| S4 | CI/CD GitHub Actions · QA gates · Conventional Commits |
| S5 | Console v2 · modo demo/API · export ZIP · bundle de evidências |
| S6 | Validação XML · Findings/Evidence v1.1 · workflow de exceções |
| S7 | 10 regras NT 2025.002 · 14 CSTs · CrewAI hardening · runbook QA |
| S8 | Relatório auditável PDF · Superpowers skills · CrewAI reliability |
| S9 | Domínio tribultz.com.br · Cloudflare DNS/CDN · Vercel deploy |
| S10 | Billing Asaas · 5 planos · webhooks · usage tracking |
| S11 | Upload de documentos · S3 presigned URLs · extração XML |
| S12 | Freemium: diagnóstico público (3 findings) · funil de conversão |
| S13 | Registro multi-tenant · consent empresarial/contador · Turnstile |
| S14 | Calculadora CBS/IBS · 14 regras S11–S13 · snippet XML para ERP |
| S15 | API pública pay-per-call (`POST /api/v1/public/classify`) · créditos API · API keys |
| S16 | ERP Export multi-formato (TOTVS, SAP, Omie, Linx, CSV) |
| S17 | NCM Auto-classify via IA (`POST /ncm/suggest`) · SEO optimizado |
| S18 | Dual-regime comparison ICMS/PIS/COFINS vs CBS/IBS (jobs) |
| S19 | Split Payment Dashboard · rastreabilidade crédito CBS/IBS por NF |
| S20 | Credits Dashboard (saldo IBS/CBS por período) |
| #268 | Monitoring contínuo · GitHub Actions uptime check 5min · alerta email |
| #269 | Billing recorrente Asaas · notificações trial D-3/D-1/expirado · fix login pós-pagamento |
| #270 | CRM Engagement Crew · HubSpot lifecycle automático · dunning e win-back via CrewAI |
| #273 | Fix SQL syntax 500 no dashboard — `CAST(:param AS type)` em sqlalchemy.text() |
| #274 | cClassTrib SVRS — migration 75 códigos · regulamentos 30/abr/2026 · `last_synced_at` |
| #279 | Diff regulamentos IBS/CBS 30/abr/2026 × 22 regras · `docs/regulamentos_2026_diff.md` |
| #280 | Deploy automático `alembic upgrade head` · `--no-deps` para zero-downtime Redis |
| #282 | HubSpot tracking code — portal 49735644 · pageviews em todas as páginas |
| #283–284 | HubSpot CRM sync · deal stages pipeline padrão · deduplicação via search API |
| #285 | **Modo Período Educativo LC 227** · toggle tenant · badge ⚖️ · 14 regras acessórias |
| #287 | **dPrevEntrega** · Rejeição 1157 preventiva · divergência competência CBS/IBS · CIF alert |
| #288–289 | **Simulador de Impacto** · `/simulador` público · endpoint `POST /simulator/regime` |
| Infra | Magalu Cloud · docker-compose.prod · rolling deploy · SecDevOps |

### Em andamento

| Item | Descrição | Prioridade |
|---|---|---|
| `no-new-privileges` + `cap_drop` | Adicionar ao docker-compose.prod.yml | Alta |
| `unattended-upgrades` | Patches automáticos de segurança na VM | Média |
| CEST × tabela ST (#275) | Cruzar NCM com tabela CEST/CONFAZ para identificar produtos ST | P1 |
| MONOFASICO_ZERO (#278) | CST 620 downstream deve ter vCBS=vIBS=0 | P2 |
| Simulador Fase B | Regimes diferenciados, cashback, setor específico por NCM | P2 |

### Próximos sprints

| Sprint | Funcionalidade | Impacto |
|---|---|---|
| S15 | **Calculadora Oficial Serpro** — cross-validation com API gov.br quando credenciais disponíveis | Alto |
| S16 | **Upload em lote** — arrastar N XMLs · progresso em tempo real · relatório consolidado | Alto |
| S17 | **Analytics Dashboard** — gráficos de tendência · erros mais frequentes · evolução de créditos | Médio |
| S18 | **Webhook API pública** — notificações por HTTP para integração com ERPs | Médio |
| S19 | **Gov.br SSO** — login via conta Gov.br para validação de identidade CNPJ | Alto |
| S20 | **SDK Python/JS** — cliente oficial para integração programática | Médio |
| S21 | **Integração SPED** — importar SPED Contribuições para validação bulk | Alto |
| S22 | **NF-e emissão** — gerar e enviar NF-e conforme NT 2025.002 diretamente ao SEFAZ | Alto |

---

## Contribuindo

### Fluxo de trabalho

```bash
# 1. Criar branch da issue
git checkout -b feat/s15-calculadora-oficial

# 2. Desenvolver com testes primeiro (TDD)
# 3. Rodar gates antes do PR
cd backend && python -m pytest tests/ -q && ruff check app/ tests/
cd frontend && npm test --silent && npm run build

# 4. Commit (Conventional Commits)
git commit -m "feat(s15): integrar calculadora Serpro via OAuth gov.br"

# 5. Abrir PR — um PR por issue
```

### Convenções

| Item | Padrão |
|---|---|
| Commits | `feat(sN):` · `fix(sN):` · `chore(sN):` · `docs(sN):` |
| Branches | `feat/issue-slug` · `fix/bug-slug` |
| PR | Um por issue · gates devem passar |
| Tabelas multi-tenant | Toda tabela nova exige `tenant_id UUID NOT NULL REFERENCES tenants(id)` |
| Endpoints auth | Sempre usar `current_user.tenant_id`, nunca `tenant_slug` de path param |
| Secrets | Nunca commitar `.env` ou credenciais — `.gitignore` enforça |

---

## Licença

Software proprietário. Todos os direitos reservados © 2026 Tribultz.

Para licenciamento comercial: contato@tribultz.com.br

---

<div align="center">
  <strong>tribultz.com.br</strong> · Conformidade CBS/IBS para a Reforma Tributária Brasileira
</div>
