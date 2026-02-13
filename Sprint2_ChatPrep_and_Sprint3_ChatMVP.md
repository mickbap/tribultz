# TRIBULTZ — Chat no Console: Chat Prep (Sprint 2) + Chat MVP (Sprint 3)

## Decisão
O chat acontecerá **sempre dentro do Console (Next.js)**.

## Objetivo
Introduzir uma camada conversacional/operacional **sem comprometer P0 da Sprint 2** (Auth/Tenant/Alembic/Testes).
- **Sprint 2:** preparar terreno (scaffold + contrato + trilha auditável) — **sem execução real obrigatória no produto**.
- **Sprint 3:** entregar Chat MVP operacional no Console com 1 fluxo end-to-end.

---

## Sprint 2 — Chat Prep (P1 opcional, baixo risco)
**Regra de ouro:** só entra como “prep” (infra/contrato). Nada de lógica fiscal no LLM.

### Entregáveis
1) **Scaffold CrewAI (ChatOps)**
- Diretório: `crews/tribultz_chatops/`
- Estrutura mínima:
  - `README.md` (como rodar + modo DRY_RUN)
  - `config/agents.yaml`
  - `config/tasks.yaml`
  - `tools/` (apenas read-only e/ou DRY_RUN safe)
  - `crew.py` (Sequential)
  - `main.py` (DRY_RUN=1 por default)

2) **Contrato padronizado de retorno das Tools**
Formato padrão (texto/JSON serializado) para qualquer tool:
- `ok: bool`
- `code: str`
- `message: str`
- `retryable: bool`
- `evidence: object` (job_id, audit_id(s), urls, timings)

3) **Padrão de Auditoria para ações do Chat**
- Definir convenção de action names (ex.: `chat.validate.trigger`, `chat.jobs.status`, `chat.audit.search`)
- Garantir que qualquer “ação” do chat referencie:
  - `tenant_id` (do token)
  - `user_id` (sub do token)
  - `conversation_id` (quando existir)
  - checksums e metadata relevantes

4) **Stub UI no Console (feature-flag)**
- Criar rota `/chat` com UI mínima (placeholder) atrás de flag (ex.: `NEXT_PUBLIC_CHAT_ENABLED=false`)
- Sem chamadas reais ao backend ainda (ou apenas mock).

### DoD Sprint 2 (Chat Prep)
- Nenhuma alteração em deps de produção
- Scaffold existe e roda em `DRY_RUN=1` com saída que lista “plano de execução” sem executar comandos destrutivos
- Contrato de Tool Result documentado e aplicado nas tools do scaffold
- Stub `/chat` no Console atrás de feature-flag

---

## Sprint 3 — Chat MVP (Console Operável)
Entregar chat funcional end-to-end com **um fluxo** e evidências auditáveis.

### Fluxo MVP (único)
**“Validar CBS/IBS”**
- Usuário conversa no Console
- Chat coleta inputs mínimos
- Dispara Task A (validate + audit)
- Acompanha Job até conclusão
- Retorna resumo humano + evidências (job_id + links Audit)

### Componentes
1) **Backend**
- Endpoint: `POST /api/v1/chat/message`
  - JWT obrigatório
  - tenant scoping **somente** do token
  - retorna: resposta + `evidence[]`
- Integração com Jobs/Audit existentes (sem duplicar lógica)

2) **CrewAI ChatOps**
- Agents:
  - Triage (entender intenção / escolher fluxo)
  - Operator (executar via tools)
  - Narrator (resumir + evidências)
  - Guardrails (RBAC + escopo)
- Tools (via API interna):
  - trigger Task A
  - get job status
  - search audit logs

3) **Console UI**
- Tela `/chat` real (input, histórico, status)
- Render de “ações/evidências” (job links, audit links)
- Mensagens de erro padronizadas (com code + retryability)

### DoD Sprint 3 (Chat MVP)
- Chat no Console funcional (1 fluxo)
- Tenant/RBAC enforced server-side
- Toda ação gera evidência auditável (job/audit)
- Testes mínimos:
  - 1 teste integração do endpoint `/chat/message` (mock tool ou ambiente controlado)
  - 1 teste e2e leve no Console (opcional, se couber)

---

## Critério de Go/No-Go (Sprint 2 → Sprint 3)
O Chat MVP só inicia quando:
- Auth + tenant scoping + RBAC mínimo estiverem estáveis
- Alembic inicial ativo e pipeline previsível
- Jobs/Audit confiáveis no CI (smoke + integração mínima)
