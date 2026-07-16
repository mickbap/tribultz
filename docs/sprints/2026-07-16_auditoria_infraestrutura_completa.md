# Auditoria Completa de Infraestrutura — Encerramento do Incidente 09/07–16/07/2026

Data: 2026-07-16
Contexto: Etapa 1 da consolidação pós-incidente (ver `docs/sprints/2026-07-15_infra_dev_env_mac_migration.md` para a fase de acesso/dev-env; issue [#432](https://github.com/mickbap/tribultz/issues/432) — Owner Workstation Recovery).

## 1. Deploy

- **Backend**: `deploy-prod.yml` → SSH → `deploy.sh` na VM. Deploy controlado disparado manualmente em 16/07 (run [`29467289172`](https://github.com/mickbap/tribultz/actions/runs/29467289172)): **sucesso total, 33s** (pull 1s, build 2s, migração 2s, API healthy 14s, worker 9s, beat 5s).
- **Achado real**: o deploy automático anterior (run `29464934375`, merge do PR #453) **falhou** — não por firewall/SSH (a causa histórica de #436), mas porque `git pull --ff-only` encontrou uma mudança local não commitada na VM (`infra/docker-compose.prod.yml`) e abortou **antes de tocar em qualquer container** (`set -euo pipefail` funcionou como esperado — falha segura, sem impacto em produção). Corrigido na hora via reconciliação manual do working tree + o próprio PR #453. Deploy seguinte (acima) confirma a cadeia saudável de ponta a ponta.
- **Frontend**: Vercel via GitHub App — deploys recentes todos `Ready` (confirmado em sessão anterior).

## 2. Rollback

- `deploy.sh` salva snapshot `:rollback` de cada imagem antes do build; restaura automaticamente se o health check pós-restart falhar.
- Não exercido nesta consolidação (nenhum deploy falhou depois de reconciliada a VM) — mecanismo íntegro por inspeção de código, não testado em produção real neste ciclo.

## 3. Git

- `main` e a VM (`/opt/tribultz`) **reconciliados**: mesmo commit (`bafcdf6` após o deploy de validação), `git status` limpo nos dois lados.
- Ownership misto identificado no `.git` da VM (`FETCH_HEAD` de `root`, resto de `ubuntu` — resultado de o `deploy.sh` rodar via `sudo`) — sem impacto funcional, registrado para conhecimento.

## 4. Docker / Compose

- Local (Mac): imagens rebuildadas, stack completo (`db`/`redis`/`minio`/`api`/`worker`/`beat`) saudável.
- Produção: imagens sempre reconstruídas a cada deploy (`build --pull` no `deploy.sh`) — não sofre o problema de cache do ambiente local.
- Rede do compose de produção unificada (`internal`→`tribultz`, PR #453) — sem mais divergência entre o que roda e o que está no repo.

## 5. GitHub Actions

- `ci.yml` (backend-gates + frontend-build): verde nos últimos PRs.
- `deploy-prod.yml`: confirmado funcional (ver seção 1).
- `monitor.yml`, `classtrib-sync.yml`, `soro-blog-sync.yml`: não auditados nesta rodada (fora do escopo do incidente).

## 6. Vercel

- CLI autenticado, projeto resolve, deploys `Ready`. Next.js 16.2.10 já na última versão.
- **Pendência conhecida, não nova**: issue [#435](https://github.com/mickbap/tribultz/issues/435) — auto-deploy da Vercel via GitHub App ainda não revalidado desde o incidente de 09-10/07 (publicação naquele momento foi manual via `vercel deploy --prod`). Não foi possível confirmar nesta sessão se o gatilho automático (push→produção) já voltou sozinho ou segue exigindo o passo manual — **recomendo validar com um push real e observar se a Vercel publica sozinha**, antes de fechar #435.

## 7. Magalu (VM)

- Kernel atualizado (reboot coordenado, 16/07), sem reboot pendente, sem OOM em 30 dias, disco com folga.
- `/health/deep` (local e externo): todos os subsistemas `ok`.

## 8. Command Center, Founding Partners, Partner Attribution (auditoria de código)

**Implementados de verdade, não só documentados:**
- Command Center: `backend/app/routers/admin.py` (739 linhas) + `founding_partners.py` (356 linhas), 8 páginas em `frontend/src/app/admin/`.
- Founding Partners / Grant Adapter (ADR-0008): `backend/app/models/founding_partner.py` — `EarlyGrant`, `resolve_effective_license`, consumido em `auth.py` no login.
- Partner Attribution (RFC-0025): `backend/app/models/partner.py`, captura `?partner=`/`?ref=` em `frontend/src/app/register/page.tsx`.
- **31 testes** cobrindo os três fluxos (`test_admin_access.py`, `test_partner_admin.py`, `test_founding_partners_admin.py`, `test_partner_code.py`). Nenhum TODO/FIXME/mock encontrado.

## 9. TERA — achado relevante

**Não implementado.** RFC-0018 (tribultz-brain) está com status `proposed`. No código do produto, "TERA" existe **somente como copy de marketing** na landing `/founding-partners` (duas strings estáticas). Não há Fiscal Readiness Index, endpoint, service, model ou teste. Isso é relevante porque TERA é a prioridade #3 declarada para depois desta consolidação — vale registrar que ainda é 100% trabalho futuro, não uma funcionalidade pausada por causa do incidente.

## 10. APIs, Workers, Schedules — inventário

- **28 routers** ativos (lista cresceu desde a documentada no `CLAUDE.md` — ver Etapa 5/achado de doc desatualizada). Router `chat` não existe mais (virou crew CrewAI, não endpoint REST).
- **10 tasks Celery**, **6 schedules** no beat (`expire-trials-hourly`, `warn-trial-expiring`, `reset-usage-monthly`, `classtrib-sync-weekly`, `compliance-monthly-scores`, `crm-audit-daily`).
- **Achado real**: `task_f_security_audit.py` está **órfã** — não aparece em `autodiscover_tasks`, sem entrada em `beat_schedule`, não referenciada em lugar nenhum. Definida mas nunca executada por nada. Recomendo abrir issue própria para decidir: registrar no beat, ou remover se obsoleta.

## Achados que exigem decisão (não corrigidos nesta auditoria — fora do pedido de "só medir/registrar")

1. `task_f_security_audit.py` órfã.
2. `CLAUDE.md` com lista de routers desatualizada (seção "Estrutura do projeto").
3. Issue #435 (auto-deploy Vercel) não revalidada nesta sessão.

## Pendências conhecidas — registradas, sem intervenção (decisão explícita já tomada)

- Chave Resend revogada (HTTP 401).
- `GITHUB_TOKEN` de produção é o OAuth pessoal do usuário.
- `gh` CLI sem escopo `workflow`.
- Inventário completo de credenciais: `docs/infra/secrets_inventory.md`.

Nenhuma ação foi tomada nessas pendências, por ordem vigente documentada em `docs/context/feedback_no_token_rotation.md`.
