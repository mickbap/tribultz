# Runbook Operacional — Tribultz

> Consolidação pós-incidente (09/07–16/07/2026). Fonte de verdade operacional do
> repositório `tribultz`. Decisões de negócio/processo vivem no `tribultz-brain`
> (`knowledge/operations/`); este documento é a camada de execução técnica.

## Arquitetura atual

```
                    ┌─────────────┐
                    │   GitHub    │
                    │    main     │
                    └──────┬──────┘
              ┌────────────┼────────────┐
              ▼                         ▼
    ┌───────────────────┐    ┌────────────────────┐
    │  Vercel (GitHub    │    │  GitHub Actions     │
    │  App integration)  │    │  deploy-prod.yml    │
    │  → frontend        │    │  → SSH → VM Magalu  │
    └───────────────────┘    └──────────┬──────────┘
                                         ▼
                              ┌─────────────────────┐
                              │ VM tribultz-api      │
                              │ (Ubuntu 24.04,       │
                              │  Magalu br-se1)      │
                              │ docker-compose.prod  │
                              │ → api/worker/beat/   │
                              │   redis              │
                              └──────────┬───────────┘
                                         ▼
                          PostgreSQL (Magalu DBaaS, externo)
                          Object Storage (Magalu S3, externo)
```

- **Frontend**: Next.js, deploy via integração GitHub App da Vercel (não passa pelo workflow `deploy-prod.yml`).
- **Backend**: FastAPI + Celery/Redis em containers Docker na VM; Postgres e Object Storage são serviços gerenciados externos (DBaaS/S3), não containers.
- **CI**: `ci.yml` (backend-gates + frontend-build) roda em todo PR/push.

## Fluxo de deploy (backend)

Gatilho: push em `main` que toca `backend/**` ou `infra/**`, ou `workflow_dispatch` manual.

1. `.github/workflows/deploy-prod.yml` faz checkout, configura chave SSH temporária (secret `MAGALU_SSH_KEY`), conecta em `ubuntu@<MAGALU_SSH_HOST>`.
2. Executa `sudo bash /opt/tribultz/infra/scripts/deploy.sh` na VM, que roda **sequencialmente** (`set -euo pipefail` — para no primeiro erro):
   1. `git pull --ff-only` (aborta com erro se houver mudança local não commitada no working tree da VM — ver "Regra de origem" abaixo)
   2. `docker compose build --pull`
   3. `alembic upgrade head` (idempotente)
   4. Restart `api` com `--no-deps`, aguarda `healthy`, valida `/health` via HTTP
   5. Restart `worker`
   6. Restart `beat`
3. Rollback automático por serviço se o health check falhar (restaura snapshot de imagem `:rollback` salvo antes do build).

**Tempo de referência** (deploy controlado, 16/07/2026, run [`29467289172`](https://github.com/mickbap/tribultz/actions/runs/29467289172), commit `bafcdf6`, sem mudança de código): pull 1s → build 2s (cache, sem mudança) → migração 2s (no-op) → API healthy 14s → worker 9s → beat 5s. **Total: 33s**.

## Rollback

- **Automático por serviço**: se o health check de `api` falhar após um deploy, `deploy.sh` restaura a imagem `:rollback` (snapshot salvo antes do build) e reinicia o serviço.
- **Rollback de código**: `git -C /opt/tribultz revert HEAD && bash infra/scripts/deploy.sh --skip-pull` (instrução já impressa pelo próprio script em caso de falha).
- **Migração**: `infra/scripts/db-migrate.sh --prod` faz backup `pg_dump` antes de qualquer `alembic upgrade head` fora do fluxo padrão do deploy.

## Regra de origem de mudanças (adotada em 16/07/2026)

> **Produção nunca deve conter alteração que não exista no Git.** Toda mudança
> operacional nasce do repositório — nunca é feita direto na VM.

**Motivo**: um incidente real (16/07/2026) mostrou o custo dessa violação — `infra/docker-compose.prod.yml` foi editado diretamente na VM (rede renomeada `internal`→`tribultz`, provavelmente para resolver DNS interno) sem nunca ser commitado. Isso **quebrou um deploy automático real** (run `29464934375`, PR #453): `deploy.sh` abortou no passo `git pull --ff-only` com `Your local changes... would be overwritten by merge`. Nenhum container chegou a ser tocado (o script parou antes do build) — mas o deploy automático falhou até a divergência ser trazida para o repo via PR e o working tree da VM ser reconciliado manualmente (`git checkout -- <arquivo> && sudo git pull --ff-only`).

**Como aplicar:**
- Qualquer mudança de configuração de infra (compose, nginx, firewall, etc.) vira PR no repo primeiro. A VM só recebe via `git pull`.
- Se uma mudança emergencial precisar ser feita direto na VM (ex.: indisponibilidade), ela **deve** ser trazida ao repo via PR na sequência imediata — nunca deixada solta no working tree.
- `tools/check_access.sh` e este runbook devem ser consultados antes de qualquer deploy manual.

## Recuperação de ambiente (bootstrap de máquina nova)

Runbook completo de onboarding (SSH, `mgc`, `gh`, Vercel, `.env.prod`) em `docs/infra/secrets_inventory.md` (seção "Onboarding em máquina nova"). Resumo:

1. Chave SSH própria da máquina, autorizada na VM a partir de uma máquina que já tenha acesso (nunca sobrescrever chave existente).
2. `mgc` CLI + `mgc auth login` (sessão OAuth) — atenção à armadilha dos dois tenants Magalu (ver `secrets_inventory.md`).
3. `.env.prod` sempre puxado da VM (`/opt/tribultz/.env`, fonte de verdade) — nunca copiado de outra máquina.
4. `gh auth login`, `vercel login`.
5. Validar tudo com `bash tools/check_access.sh` antes de depender da máquina.

Bootstrap de infra do zero (VM nova): `infra/scripts/magalu-init.sh` — instala Docker, UFW, fail2ban, nginx, certbot, roda migrations e sobe o stack.

## Checklist de auditoria operacional

Rodar antes de considerar a infraestrutura saudável:

- [ ] `bash tools/check_access.sh` — SSH, `mgc`, `gh`, Vercel, drift do `.env.prod`, produção no ar.
- [ ] `git status` limpo tanto no repo local quanto em `/opt/tribultz` na VM (via SSH).
- [ ] `docker compose -f infra/docker-compose.prod.yml ps` na VM — todos os serviços `Up`/`healthy`.
- [ ] `curl https://api.tribultz.com.br/health/deep` — todos os subsistemas `ok`.
- [ ] `apt list --upgradable` na VM + `/var/run/reboot-required` — sem reboot pendente crítico.
- [ ] Alembic head na VM == head do repo (`alembic current` dentro do container `api`).
- [ ] Último run de `deploy-prod.yml` (`gh run list --workflow=deploy-prod.yml`) com `conclusion: success`.

## Ambientes

Não existe ambiente de **staging** — só `local` (Docker Compose do desenvolvedor, Postgres/Redis/MinIO containerizados) e `produção` (VM Magalu, Postgres/S3 gerenciados). Diferenças **intencionais** (arquitetura, não drift):

| | Local | Produção |
|---|---|---|
| Postgres | Container `postgres:16-alpine` | Magalu DBaaS (gerenciado, externo) |
| Object Storage | MinIO container | Magalu Object Storage (S3, externo) |
| Rebuild de imagem | Manual (`docker compose build`/`--build`) | Automático a cada deploy (`build --pull` no `deploy.sh`) |
| Rede Docker | `tribultz` (bridge) | `tribultz` (bridge) — unificada em 16/07/2026, ver histórico |
| Migração | `migrate` (serviço one-shot no compose) | `alembic upgrade head` como passo do `deploy.sh` |
