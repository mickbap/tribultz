# Tribultz Weekly Snapshot — Semana {{WEEK}}

- **Data:** {{DATE}}
- **Ref:** `{{BRANCH}} @ {{REF}}`
- **Gerado por:** `tools/operational-baseline/operational_baseline.sh` (hábito: toda sexta)

> **Produto mede, Brain interpreta.** Este documento contém **apenas fatos** —
> nenhuma análise. A interpretação da semana (aprendizado, risco, decisão,
> evidência, prioridade, hipóteses derrotadas) vive no Brain: `tribultz-brain`
> → `knowledge/discovery/weekly/AAAA-Wnn.md` (RFC-0023).

## Produto
| Métrica | Valor |
|---|---|
| Regras determinísticas (`RULES_COUNT`) | {{RULES}} |
| cClassTrib (`CLASSTRIB_COUNT`) | {{CLASSTRIB}} |
| Routers (backend) | {{ROUTERS}} |
| Endpoints (rotas) | {{ENDPOINTS}} |
| Páginas (frontend) | {{PAGES}} |

## Infraestrutura
| Métrica | Valor |
|---|---|
| Migrations (arquivos) | {{MIGRATIONS}} |
| Migrations pendentes | {{PENDING_MIGS}} |
| Health — storage probe | {{STORAGE_PROBE}} |

## Dados
| Métrica | Valor |
|---|---|
| Usuários | {{USERS}} |
| Empresas (tenants) | {{TENANTS}} |
| API Keys | {{APIKEYS}} |
| Laudos gerados | {{LAUDOS}} |
| XML processados | {{XMLS}} |

## Saúde
| Métrica | Valor |
|---|---|
| TODO/FIXME no código | {{TODOS}} |
| Issues abertas | {{ISSUES_OPEN}} |
| Issues P2 (prioritárias) | {{ISSUES_P2}} |
| RFCs abertas | {{RFCS}} |

## Capacidades em produção (Fase 1)
| Capacidade | Referência | Desde |
|---|---|---|
| Partner Attribution | RFC-0025 | 2026-07-08 |
| EarlyAdopter | RFC-0017 | 2026-07-08 |
| EarlyGrant | ADR-0008 | 2026-07-08 |
| EffectiveLicense | ADR-0008 | 2026-07-08 |
| Programa Founding Partners | RFC-0017 | 2026-07-08 |

## Motor / Known Limitations (Fase 1 — por design)
| Item | Ocorrências | Destrava |
|---|---|---|
| TERA | {{TERA}} | RFC-0018 |

_Deve ser 0 na Fase 0. Quando passar de 0, a Fase 1 daquele item começou a existir._

## Próxima prioridade
{{NEXT_PRIORITY}}

---

_Fatos apenas. Interpretação da semana → `tribultz-brain` `knowledge/discovery/weekly/` (RFC-0023: Produto mede, Brain interpreta)._
