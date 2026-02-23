# Sprint 5 Console v2 — Relatório Detalhado (P0+P1)

Data: 2026-02-23
Branch: feat/s5-close-gaps-auth-audit-ptbr

## 1) Comandos executados e resultados

```bash
cd frontend
npm install
npm run build
```
Resultado:
- `npm install`: concluído com atualização de lockfile.
- `npm run build`: PASS (rotas `/login`, `/dashboard`, `/chat`, `/jobs`, `/jobs/[id]`, `/audit`, `/settings`, `/validate`, `/report`).

Smoke técnico em `dev`:
- Inicialização com `npm run dev -- --port 3010`.
- Health HTTP das rotas principais:
  - `/login` => 200
  - `/dashboard` => 200
  - `/chat` => 200
  - `/jobs` => 200
  - `/audit` => 200
  - `/settings` => 200

## 2) Smoke do fluxo principal

### Mock Mode
PASS (wiring e navegação implementados):
1. Login Demo ativa Mock Mode e tenant.
2. Dashboard carrega KPIs, últimos jobs e auditorias.
3. Chat envia CTA "Validar CBS/IBS..." e renderiza markdown/evidências.
4. Link de evidência abre `/jobs/[id]`.
5. Job detail possui link para `/audit?job_id=...`.
6. `/audit` agora carrega por `job_id` quando informado na URL.

### API Mode
Parcial (dependente de backend/credenciais):
- Caminho de login real reintroduzido em `/login` via `POST /api/v1/auth/login`.
- Em caso de sucesso, salva `access_token`, desliga Mock Mode e mantém tenant.
- Requests em API Mode seguem com `Authorization: Bearer <token>` e `X-Tenant-Id`.
- Limitação: sem credenciais válidas neste ambiente para validar login ponta a ponta.

## 3) Arquivos/rotas removidos ou mantidos por decisão

### Removidos (legado não usado no Sprint 5)
- `frontend/src/auth/*`
- `frontend/src/services/api.ts`
- `frontend/src/types/audit.ts`
- `frontend/src/types/jobs.ts`
- `frontend/src/app/NavBar.tsx`
- `frontend/src/app/chat/chat.module.css`

### Mantidos com redirecionamento explícito
- `/validate` -> redireciona para `/chat`
- `/report` -> redireciona para `/jobs`

Motivo: preservar compatibilidade de rota sem manter UX legado fora do escopo Sprint 5.

## 4) Ajustes obrigatórios aplicados

1. Auth mock + real no `/login`:
   - `Entrar (Demo)` mantém Mock Mode ON.
   - `Entrar (API)` chama `/api/v1/auth/login`.
   - Persistência de token e tenant para API Mode.

2. `/audit?job_id=`:
   - Quando `job_id` existe na URL, usa `getAudits(jobId)` no carregamento.
   - Filtros adicionais continuam no cliente.

3. PT-BR:
   - Configurações, auditoria, detalhe do job e labels principais em PT-BR.
   - CTA do Chat em PT-BR alinhada ao manifesto.

4. Higiene de legado:
   - remoção de arquivos antigos não usados + redirects para rotas legadas.

## 5) DoD checklist (P0+P1)

- [x] Roda local em Mock Mode (`npm run dev`)
- [x] Build passa (`npm run build`)
- [x] Sem segredos no front
- [x] Fluxo principal: Login -> Dashboard -> Chat -> Validar -> Job -> Audit
- [x] Estados `loading/empty/error` nas telas principais
- [x] A11y mínimo (focus visível, labels e controles principais)
- [x] API Mode envia `Authorization` + `X-Tenant-Id`

## 6) Limitações conhecidas

- Validação completa de login real (API Mode) depende de backend disponível + credenciais válidas.
- Não foi incluído ajuste de design P2 além do necessário para consistência PT-BR e usabilidade.
