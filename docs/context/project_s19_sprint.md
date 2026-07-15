---
name: project_s19_sprint
description: "Estado do backlog S20/S21 — sessão 17/05/2026: #175 e #173 mergeados em prod, prioridades atualizadas com pesquisa competitiva"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f924a49-e6b8-433d-86d6-78f4c30337a6
---

## Estado em 17/05/2026 (atualizado)

### PRs mergeados nesta sessão

| PR | Branch | Issue | Alembic |
|----|--------|-------|---------|
| #255 | `feat/175-public-api-classify` | #175 API pública pay-per-call | migration 0016 aplicada em prod |
| #256 | `feat/173-erp-export-formats` | #173 ERP Export por jobs | sem migration nova |
| #259 | `feat/site-update-may2026` | site marketing | aguardando CI |

### Deploy prod

- Deploy automático disparado e concluído para ambos os PRs (#255 e #256)
- `alembic upgrade head` executado: `2026_05_17_0016 (head)` — tabela `api_keys` em produção
- SSH: `ubuntu@201.54.20.18` com `id_ed25519`; compose em `/opt/tribultz/infra/docker-compose.prod.yml`

### Backlog priorizado (pesquisa competitiva mai/2026)

| # | Título | Prioridade | Motivo |
|---|--------|-----------|--------|
| #170 | NCM Auto-classify via IA | **P1** | Maior dor não resolvida do mercado; nenhum concorrente tem; temos fundação (#175) |
| #257 | Dual-regime report (PIS/COFINS vs CBS/IBS) | P2 | Diferenciador vs Sovos; CFOs precisam |
| #169 | Split Payment Dashboard | P2 | Dor do CFO; janela até 2027; nenhum concorrente cobre bem |
| #258 | Credit tracking dashboard | P2 | Sticky feature; Thomson Reuters só enterprise |
| #225 | Refactor jobs.py ORM | P3 | Debt técnico |

### Issues novas criadas (pesquisa mai/2026)

- **#257** — Dual-regime report (exibir PIS/COFINS + ICMS lado a lado com CBS/IBS)
- **#258** — Credit tracking dashboard (rastreabilidade de crédito por operação)

### Pesquisa competitiva mai/2026 — achados-chave

- **Maior gap de mercado**: NCM → cClassTrib automatizado com evidência legal — não existe hoje
- **Urgência real**: penalidades CBS/IBS a partir de ago/2026 (era "período educacional" antes)
- **Concorrentes principais**: Sovos (pre-clearance + dual-regime), Thomson Reuters (enterprise), Tecnospeed/PlugNotas (middleware para software houses)
- **Nosso diferenciador**: validação pós-fato com evidência auditável + API classify + export ERP multi-formato
- **Emerging threat**: Tax Radar (taxradar.app) — startup construindo mapeamento NCM/cClassTrib; monitorar

### Infra — estado em 17/05/2026

- VM Magalu: ubuntu@201.54.20.18, compose em /opt/tribultz/infra/docker-compose.prod.yml
- Containers: infra-api-1, infra-worker-1, infra-beat-1, infra-redis-1
- Alembic head: 2026_05_17_0016 (add_api_keys)
- Branch main: commit após merge #256
