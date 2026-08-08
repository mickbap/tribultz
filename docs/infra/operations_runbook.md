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

## Backup e Restore — Postgres (Magalu DBaaS)

**Status: já existe e está ativo** — confirmado em 19/07/2026 via `mgc dbaas instances list` +
`mgc dbaas snapshots instances-snapshots list` (#447). Não é o `pg_dump` pré-migração acima
(esse é só um extra antes de mudanças de schema); é o backup gerenciado nativo do DBaaS, que
roda independente de deploy/migração.

- **Frequência**: diária, `backup_start_at: 02:00:00` UTC (instância `tribultz`, id
  `87ae9966-6664-41c4-815f-adc90004f41a`).
- **Retenção**: 7 dias rolante (`backup_retention_days: 7`) — confirmado com 7 snapshots
  `AUTOMATED`/`AVAILABLE` reais, um por dia, 13/07 a 19/07/2026 (sem furos).
- **RPO**: até ~24h no pior caso (incidente minutos antes do próximo backup às 02:00 UTC).
- **RTO**: não medido. Restore cria uma **instância nova** (não é in-place — ver runbook
  abaixo), então o RTO real depende do tempo de provisionamento Magalu + repontar `.env` +
  restart dos serviços. Nenhum drill de restore foi executado; recomenda-se agendar um teste
  real (fora do horário de pico) para medir um número confiável em vez de estimar.
- **Destino**: fora da VM — serviço gerenciado Magalu, isolado do `tribultz-api`; sobrevive a
  qualquer incidente na VM (disco, container, SO).
- **Proteção adicional**: `deletion_protected: true` na instância — não pode ser apagada sem
  desabilitar essa flag primeiro.

**Comandos de verificação:**
```bash
# Config de backup da instância (retenção, horário, proteção)
mgc dbaas instances list -o json

# Snapshots automáticos disponíveis
mgc dbaas snapshots instances-snapshots list --instance-id=<INSTANCE_ID> --type=AUTOMATED -o json
```

**Runbook de restore** (instância nova a partir de snapshot — a Magalu não sobrescreve a
instância existente):

1. Escolher o snapshot: `mgc dbaas snapshots instances-snapshots list --instance-id=<ID>`.
2. Criar a instância nova a partir dele:
   ```bash
   mgc dbaas snapshots instances-snapshots restore <INSTANCE_ID> <SNAPSHOT_ID> \
     --name=tribultz-restore-<DATA> \
     --instance-type-id=55e5a3f5-ff08-4b1d-9ac6-d568224f2529 \
     --volume.size=20 --volume.type=CLOUD_NVME15K
   ```
3. Aguardar `status: ACTIVE` (`mgc dbaas instances list`) e anotar o novo endereço de conexão.
4. Validar os dados na instância nova **antes** de promovê-la: `psql` direto, contagens de
   tabelas-chave, `alembic current` batendo com o head do repo.
5. Repontar produção: atualizar `POSTGRES_HOST` (e demais `POSTGRES_*`) em
   `/opt/tribultz/.env` para a instância nova, reiniciar os serviços que conectam ao banco
   (`docker compose -f infra/docker-compose.prod.yml restart api worker beat`).
6. Manter a instância antiga por um período de segurança (investigação/forense) antes de
   decidir removê-la — decisão manual, não automatizada.

**Redis (`redis_data`, broker Celery)**: sem rotina de backup dedicada — decisão deliberada,
não lacuna. Redis aqui é só broker/cache Celery (fila de tasks + rate limiting), não guarda
dado de negócio durável (isso vive inteiramente no Postgres). Perder o AOF num incidente
perde, no pior caso, tasks em voo — recuperável reprocessando a origem (webhook, upload).
Fora do critério de aceite do #447, que é especificamente sobre Postgres.

**Por que não um pipeline `pg_dump` → S3 adicional**: a correção original do #447 propunha
isso como fallback *se* o DBaaS não tivesse backup gerenciado. Como tem (confirmado acima),
um segundo pipeline seria redundância sem ganho real de proteção — mais uma rotina para
manter, sem reduzir RPO/RTO de forma material. Revisitar só se o backup gerenciado da Magalu
for descontinuado, ou se uma auditoria de compliance exigir backup fisicamente fora da
Magalu (multi-provedor).

## Regra de origem de mudanças (adotada em 16/07/2026)

> **Produção nunca deve conter alteração que não exista no Git.** Toda mudança
> operacional nasce do repositório — nunca é feita direto na VM.

**Motivo**: um incidente real (16/07/2026) mostrou o custo dessa violação — `infra/docker-compose.prod.yml` foi editado diretamente na VM (rede renomeada `internal`→`tribultz`, provavelmente para resolver DNS interno) sem nunca ser commitado. Isso **quebrou um deploy automático real** (run `29464934375`, PR #453): `deploy.sh` abortou no passo `git pull --ff-only` com `Your local changes... would be overwritten by merge`. Nenhum container chegou a ser tocado (o script parou antes do build) — mas o deploy automático falhou até a divergência ser trazida para o repo via PR e o working tree da VM ser reconciliado manualmente (`git checkout -- <arquivo> && sudo git pull --ff-only`).

**Como aplicar:**
- Qualquer mudança de configuração de infra (compose, nginx, firewall, etc.) vira PR no repo primeiro. A VM só recebe via `git pull`.
- Se uma mudança emergencial precisar ser feita direto na VM (ex.: indisponibilidade), ela **deve** ser trazida ao repo via PR na sequência imediata — nunca deixada solta no working tree.
- `tools/check_access.sh` e este runbook devem ser consultados antes de qualquer deploy manual.

**Variante legítima — configuração de SO sem trilha de deploy própria** (ex.: NTP,
timezone, kernel params: não fazem parte de compose/nginx/firewall, então não há
"PR primeiro" possível — a config só existe na VM). Legítima **sob duas condições**,
ambas obrigatórias:
1. **Backfill na mesma sessão** — o PR trazendo a mudança ao repo (script de
   bootstrap, documentação) nasce antes de a sessão de trabalho terminar, não
   "depois, quando der".
2. **PR declara o estado real** — o texto do PR diz explicitamente que a
   produção já contém a mudança (não é um PR comum "vai ser aplicado no
   deploy"); quem revisa precisa saber que está documentando o passado, não
   aprovando o futuro.

Sem as duas condições, é a mesma violação de sempre com um nome mais bonito.

**Exemplo aplicado (08/08/2026, ENG-014):** `/etc/systemd/timesyncd.conf` da VM foi
editado direto via SSH (config de NTP, não faz parte de nenhum compose/serviço —
não existia trilha de repo pra essa mudança até então) para apontar a Hora Legal
Brasileira (`a-d.st1.ntp.br`) em vez do default `ntp.ubuntu.com` — motivo:
Governança Temporal ([RFC-0030](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/rfcs/RFC-0030-governanca-temporal.md))
exige que T2 (verdade em UTC dos carimbos) rastreie a fonte regulada, não um
pool de terceiro. Trazido ao repo na sequência imediata: `infra/scripts/magalu-init.sh`
(seção "1b. NTP") agora aplica essa config em qualquer bootstrap futuro — sem
isso, uma VM nova recriada do zero voltaria silenciosamente ao default Ubuntu.

## Configuração de tempo (NTP)

VM sincronizada à **Hora Legal Brasileira** (Observatório Nacional/NIC.br, pool
`ntp.br`) via `systemd-timesyncd` — configurado em `/etc/systemd/timesyncd.conf`
(`NTP=a.st1.ntp.br b.st1.ntp.br c.st1.ntp.br d.st1.ntp.br`,
`FallbackNTP=pool.ntp.br`) e replicado no bootstrap (`infra/scripts/magalu-init.sh`,
seção "1b"). Verificar com `timedatectl show-timesync --property=ServerName --value`
— deve retornar um host `*.st1.ntp.br`, nunca `ntp.ubuntu.com`. Contexto: Governança
Temporal ([RFC-0030](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/rfcs/RFC-0030-governanca-temporal.md)) —
T2 (verdade dos carimbos) deve rastrear a fonte regulada.

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
- [ ] Snapshot automático do Postgres nas últimas 24-48h (`mgc dbaas snapshots instances-snapshots list --instance-id=<ID> --type=AUTOMATED`) — ver seção "Backup e Restore" acima.

## Ambientes

Não existe ambiente de **staging** — só `local` (Docker Compose do desenvolvedor, Postgres/Redis/MinIO containerizados) e `produção` (VM Magalu, Postgres/S3 gerenciados). Diferenças **intencionais** (arquitetura, não drift):

| | Local | Produção |
|---|---|---|
| Postgres | Container `postgres:16-alpine` | Magalu DBaaS (gerenciado, externo) |
| Object Storage | MinIO container | Magalu Object Storage (S3, externo) |
| Rebuild de imagem | Manual (`docker compose build`/`--build`) | Automático a cada deploy (`build --pull` no `deploy.sh`) |
| Rede Docker | `tribultz` (bridge) | `tribultz` (bridge) — unificada em 16/07/2026, ver histórico |
| Migração | `migrate` (serviço one-shot no compose) | `alembic upgrade head` como passo do `deploy.sh` |
