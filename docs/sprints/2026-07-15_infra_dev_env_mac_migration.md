# Migração de ambiente Windows → Mac — Acesso à infra + ciclo de desenvolvimento

Data: 2026-07-15
Branch: `chore/infra-access-validation`

## Resumo executivo

O Mac foi validado como segunda estação de trabalho operacional para o Tribultz: acesso à infraestrutura de produção (Magalu, VM, GitHub, Vercel) e ciclo de desenvolvimento local (frontend e backend) estão 100% funcionais. Um gap real de infraestrutura foi encontrado e corrigido (imagem Docker desatualizada bloqueando o ambiente local). Nenhuma credencial foi rotacionada, revogada ou teve sessão encerrada — conforme ordem vigente para esta fase do produto.

## 1) Acesso operacional à infra — resultado

| Item | Status |
|---|---|
| SSH → VM produção (`ubuntu@201.54.20.18`) | ✅ Chave própria do Mac autorizada lado a lado com a do Windows (duas chaves válidas, nenhuma revogada) |
| Magalu CLI (`mgc`) | ✅ v0.61.2 instalado, sessão OAuth própria da máquina, tenant correto selecionado |
| GitHub CLI (`gh`) | ✅ Autenticado; aviso não-bloqueante: sem escopo `workflow` (só afeta editar `.github/workflows/**` via API — via push funciona normal) |
| Vercel CLI | ✅ Autenticado |
| `.env.prod` local | ✅ Sincronizado da VM (fonte de verdade), 48 chaves |
| Produção (frontend + API) | ✅ 200/200 |

Detalhe técnico completo (fingerprints, tenants, runbook de onboarding) em `docs/infra/secrets_inventory.md`.

## 2) Ciclo de desenvolvimento local — resultado

### Frontend
- `npm ci`, `npm test --silent` (**156/156**), `npm run build` (rotas geradas, exit 0) — sem nenhum ajuste necessário.

### Backend
- `pytest tests/ -q` — **667/667 passaram**, `ruff check app/ tests/` — limpo.
- Antes da correção (seção 3), 7 testes de webhook de cobrança falhavam por dependerem de um Redis local que ainda não estava no ar — não era bug de código.

## 3) Problema encontrado e corrigido: imagem Docker desatualizada

**Sintoma**: `docker compose -f infra/docker-compose.yml up -d` subia `db`, `redis` e `minio` normalmente, mas o serviço `migrate` (que aplica as migrations Alembic antes de `api`/`worker`/`beat` subirem) falhava com `Can't locate revision identified by '2026_07_14_0026'`, e os três serviços dependentes ficavam parados.

**Causa raiz**: a imagem Docker do backend (`infra-migrate`/`infra-api`/`infra-worker`/`infra-beat`) tinha sido construída **13 dias atrás** e ficou em cache. O Docker Compose reutiliza a imagem em cache por padrão — não reconstrói sozinho quando o código muda. Nesse intervalo entraram 3 migrations novas no repositório, que a imagem antiga não conhecia.

**Correção aplicada**: `docker compose -f infra/docker-compose.yml build migrate api worker beat` seguido de `up -d`. Resultado: `migrate` concluiu com sucesso (`Exited (0)`), `api`/`worker`/`beat` subiram e ficaram saudáveis, `/health` e `/health/ready` respondendo (DB e Redis `ok`).

**Prevenção documentada**: `CLAUDE.md` atualizado (seção "Dev servers") para usar `up -d --build` e explicar por que o `--build` é necessário — ver seção 5.

## 4) Achados menores — registrados, sem ação necessária

- **MinIO local sem o bucket `tribultz`**: `/health/ready` reporta `storage: unreachable` porque o volume local do MinIO (também com 13 dias) nunca teve o bucket criado. Não afeta os gates (os testes usam storage mockado), só afeta testar upload/evidências manualmente contra o ambiente local. Correção seria criar o bucket uma vez (`mc mb`) — não fiz isso agora, fora do escopo pedido.
- **Aviso de dependência no `pip install`**: `pip-audit` (instalado à parte no venv, fora do `requirements.txt`) pede `tomli`/`tomli-w` mais novos do que o `requirements.txt` traz. Instalação não falhou, é só warning. Não é algo introduzido nesta migração.
- **Reconferido e descartado**: uma nota anterior apontava `CLAUDE.md` ainda documentando `source .venv/Scripts/activate` (caminho Windows) quebrando no Mac. Não é verdade — o histórico do git mostra que isso já tinha sido corrigido no commit `33faaab` (PR #319), antes desta migração começar. Não havia nada para corrigir aí.

## 5) Documentação corrigida (`CLAUDE.md`)

- Seção **Gates**: nota de que testes que disparam tasks Celery (`tests/test_billing_webhook.py`) exigem Redis real em `localhost:6379` — sem isso falham com `ConnectionRefusedError`, não é regressão de código.
- Seção **Dev servers**: comando trocado para `docker compose -f infra/docker-compose.yml up -d --build`, com explicação de por que o `--build` é necessário (ver seção 3).

## 6) Transparência — incidente durante a validação de acesso

Numa sessão anterior desta mesma migração, um comando (`mgc auth tenant set`) imprimiu `access_token`/`refresh_token` da sessão Magalu em texto puro no transcript do agente. Foi reportado no momento; por ordem vigente (não rotacionar/revogar/encerrar sessão nesta fase), o token permanece válido por decisão do usuário. Prevenção (redirecionar a saída desse comando) já documentada em `docs/infra/secrets_inventory.md` e aplicada nas execuções seguintes sem repetir o problema.

## Estado final da máquina

- Stack local (`infra/docker-compose.yml`) no ar: `db`, `redis`, `minio`, `api`, `worker`, `beat` todos saudáveis.
- `backend/.venv` com dependências instaladas.
- Nenhuma credencial rotacionada/revogada. Nenhum código de produto alterado — só `CLAUDE.md` e este relatório.
