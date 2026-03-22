# Sprint 8 — Superpowers + Relatório Auditável + CrewAI Hardening

> **Kickoff:** 22/03/2026
> **North Star:** Motor de validação com relatório auditável para contabilidade + workflow potencializado por Superpowers + CrewAI production-ready.
> **Milestone:** S8 (Audit Report + Superpowers Integration)

---

## Contexto

### O que já temos (S1–S7)

| Sprint | Entrega principal |
|--------|-------------------|
| S1 | Backend + Docker (Postgres, Redis, MinIO, FastAPI, Celery) |
| S2–S3 | Frontend Next.js (login, dashboard, chat, jobs, audit, settings) |
| S4 | CI verde + QA gates automáticos + template fiscal BR |
| S5 | Console v2 (mock/API mode, export ZIP, audit trail) |
| S6 | Motor de validação XML + Findings/Evidence v1.1 + Exception workflow + CrewAI chatops |
| S7 | Top 10 regras (CBS/IBS/CEST/Layout) + 3 XML exemplos + path variations + Runbook QA |

### Stack atual

- **Frontend:** Next.js 16, TypeScript, 24 testes (xmlRules)
- **Backend:** FastAPI, CrewAI (ParseNFSeXMLTool + ValidateFiscalRulesTool), 21 testes (pytest)
- **Infra:** Docker Compose (6 containers), CI GitHub Actions
- **Validação:** 10 regras determinísticas, Evidence v1.1, dual-stack (frontend mock + backend API)
- **Plugin:** Superpowers v5.0.5 instalado (14 skills)

### Dívidas técnicas herdadas

1. **Relatório auditável** — time de contabilidade pediu modelo tabular (NF | BASE ICMS | VALOR ICMS | IBS | CBS | CEST | CLASSTRIB) — não implementado
2. **CrewAI em produção** — crew chatops funciona mas não tem retry, logging estruturado, nem fallback
3. **API Mode validação** — adapter existe como placeholder, não conecta ao backend real
4. **Tela validate-xml** — mostra findings mas não gera relatório exportável para contabilidade

---

## Backlog S8

### P0 — Bloqueadores

#### S8-01 — Relatório auditável para contabilidade
**Prioridade:** P0
**Labels:** `report`, `product`, `evidence`
**Descrição:** Implementar geração de relatório tabular no formato solicitado pelo time de contabilidade. O relatório deve ser exportável (CSV + PDF) a partir dos findings de uma validação.

**Acceptance Criteria:**
- [ ] Componente `AuditReport` renderiza tabela: NF | Base Cálculo | Valor CBS | Valor IBS | CEST | ClassTrib | Status
- [ ] Cada linha mostra o resultado da validação (PASS/FAIL por campo) com cor
- [ ] Seção de findings detalhados abaixo da tabela (rule_id, severity, snippet, recommendation)
- [ ] Export CSV com todas as colunas + findings
- [ ] Export PDF (layout simples, A4 landscape)
- [ ] Funciona em Mock Mode e API Mode
- [ ] Testes unitários para formatação e cálculos

**Referência:** Formato solicitado em `memory/project_s7_accounting_feedback.md`

#### S8-02 — Integração Superpowers no workflow de desenvolvimento
**Prioridade:** P0
**Labels:** `dx`, `tooling`
**Descrição:** Configurar e validar Superpowers como workflow padrão do projeto. Criar `CLAUDE.md` com instruções do projeto + referência aos skills relevantes.

**Acceptance Criteria:**
- [ ] `CLAUDE.md` na raiz do projeto com: visão geral, stack, convenções, gates, referência a skills
- [ ] Hook `SessionStart` do superpowers funcionando
- [ ] Teste manual: nova sessão Claude Code carrega skills automaticamente
- [ ] Documentar no Runbook quais skills usar em cada situação (debugging, feature, review)

### P1 — Essenciais

#### S8-03 — CrewAI hardening (retry + logging + fallback)
**Prioridade:** P1
**Labels:** `backend`, `crewai`, `reliability`
**Descrição:** Tornar o crew chatops production-ready com retry automático, logging estruturado, e fallback quando o LLM falha.

**Acceptance Criteria:**
- [ ] Retry com backoff exponencial (3 tentativas) no crew executor
- [ ] Logging estruturado (JSON) para cada step do crew (parse → validate → narrate)
- [ ] Fallback: se LLM falha, retorna findings determinísticos (sem narrativa AI)
- [ ] Health check endpoint para o crew (`GET /api/v1/crew/health`)
- [ ] Testes unitários para retry e fallback paths
- [ ] Métricas: tempo de execução por step (log)

#### S8-04 — Wiring API Mode validação (frontend ↔ backend)
**Prioridade:** P1
**Labels:** `frontend`, `backend`, `integration`
**Descrição:** Conectar o adapter de API Mode do frontend ao endpoint real do backend para validação XML. Atualmente o adapter é placeholder.

**Acceptance Criteria:**
- [ ] Endpoint `POST /api/v1/validate` aceita XML e retorna ValidationResultV11
- [ ] Frontend API adapter chama endpoint real quando API Mode ativo
- [ ] Response inclui `invoice_id` e `s3_key` do backend
- [ ] Error handling: timeout, 4xx, 5xx com mensagens amigáveis
- [ ] Teste de integração (backend rodando + frontend chamando)

### P2 — Desejáveis

#### S8-05 — Validação em lote (batch)
**Prioridade:** P2
**Labels:** `frontend`, `product`, `ux`
**Descrição:** Permitir upload de múltiplos XMLs e gerar relatório consolidado.

**Acceptance Criteria:**
- [ ] Upload de múltiplos arquivos XML (drag & drop ou file picker)
- [ ] Validação sequencial com progress bar
- [ ] Relatório consolidado: tabela com todas as notas + total PASS/FAIL
- [ ] Export CSV/PDF do lote completo

#### S8-06 — Dashboard KPIs reais
**Prioridade:** P2
**Labels:** `frontend`, `dashboard`, `product`
**Descrição:** Alimentar dashboard com KPIs calculados a partir dos jobs reais (mock ou API).

**Acceptance Criteria:**
- [ ] Total de notas validadas (período)
- [ ] Taxa de conformidade (% PASS)
- [ ] Top 3 regras violadas (rule_id + count)
- [ ] Trend chart (últimos 7 dias)

---

## Instruções Padrão

### Convenções de código

| Item | Padrão |
|------|--------|
| Branches | `feat/s8-xxx`, `fix/s8-xxx`, `docs/s8-xxx` |
| Commits | `feat(s8):`, `fix(s8):`, `docs(s8):` — Conventional Commits |
| PRs | Título < 70 chars, body com Summary + Test Plan |
| Issues | `[S8-XX] Título` com labels e priority |
| Testes frontend | `tsx --test` (não vitest) |
| Testes backend | `pytest` dentro de `.venv` |
| Linter backend | `ruff check` |
| Build frontend | `npm run build` |

### Gates (DoD por PR)

```bash
# Frontend
cd frontend && npm test --silent && npm run build

# Backend
cd backend && source .venv/Scripts/activate && python -m pytest tests/ -q

# Lint
cd backend && source .venv/Scripts/activate && ruff check app/ tests/
```

**Nenhum PR é mergeado sem gates verdes.**

### Workflow com Superpowers

| Situação | Skill a usar |
|----------|-------------|
| Bug ou test failure | `systematic-debugging` — root cause antes de fix |
| Feature nova | `test-driven-development` — red/green/refactor |
| Plano de implementação | `writing-plans` → `subagent-driven-development` |
| Múltiplos problemas independentes | `dispatching-parallel-agents` |
| Antes de PR | `verification-before-completion` — evidência antes de claim |
| Branch pronta | `finishing-a-development-branch` — merge/PR/cleanup |
| Code review | `requesting-code-review` |

### Estrutura de diretórios relevante

```
frontend/
  src/
    app/              # Rotas Next.js (login, dashboard, chat, jobs, audit, validate-xml, etc.)
    lib/
      validation/     # Motor de validação XML (xmlRules.ts, testes, fixtures)
      types.ts        # Tipos TypeScript (Finding, ValidationResultV11, etc.)
      api.ts          # API adapter (mock/real)
      mock.ts         # Mock data e storage

backend/
  app/
    crews/
      tools/          # CrewAI tools (parse_nfse_xml, validate_fiscal_rules)
    routers/          # FastAPI endpoints
    tools/            # S3, database utilities
  tests/
    tools/            # pytest (test_nfse_tools.py)

docs/
  sprints/            # Planos, reports, discovery
    discovery/        # Top 10 consolidado + exemplos XML
    S7_Runbook.md     # Runbook operacional do motor
```

### Referências

| Recurso | Localização |
|---------|-------------|
| Runbook do motor | `docs/sprints/S7_Runbook.md` |
| Top 10 regras | `docs/sprints/discovery/S6_Discovery_Consolidated.md` |
| Exemplos + gabarito | `docs/sprints/discovery/examples/` |
| Contrato Evidence v1.1 | `frontend/src/lib/validation/findings-evidence-v1.1.schema.json` |
| Vocabulário fiscal | `memory/project_s7_vocabulary.md` |
| Base legal | LC 214 + LC 227 (13/jan/2026) |
| Alíquotas teste | CBS 0,10% · IBS 0,90% |
| Superpowers plugin | `~/.claude/plugins/superpowers/` (v5.0.5) |

---

## Ordem de execução sugerida

```
S8-02 (Superpowers setup) ──→ S8-01 (Relatório) ──→ S8-04 (API wiring)
                                                  ──→ S8-03 (CrewAI hardening)
                                                  ──→ S8-05 (Batch) ──→ S8-06 (Dashboard KPIs)
```

Começar pelo S8-02 porque estabelece o workflow que será usado em todas as outras issues.
