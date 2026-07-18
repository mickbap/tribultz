# Auditoria Contínua da Arquitetura — Ordem Técnica

Data: 2026-07-17/18
Contexto: sequência direta da institucionalização da governança arquitetural (ADR-0013, ver [relatório anterior](2026-07-17_governanca_arquitetural_adr0013.md)). Aquela ordem entregou a auditoria automatizada como ferramenta pontual; esta a transforma em processo contínuo — CI a cada PR, severidade explícita e revisão periódica da plataforma.

## 1. Decisão — 3 entregas

| Parte da ordem | Conteúdo | Onde vive |
|---|---|---|
| I — Integração ao CI | `tools/architecture_audit.py` roda no job `backend-gates`, depois de Ruff/Pyright/Pytest. **Modo informativo**: achados viram anotação `::warning::`/`::error::` no PR, mas não falham o build (`continue-on-error: true`). | `.github/workflows/ci.yml` (Produto) |
| II — Classificação de severidade | Todo achado carrega Crítico/Alto/Médio/Baixo. Política com exemplos por nível registrada no Brain; `CATEGORY_SEVERITY` no script é a aplicação dela em código. | `knowledge/process/architecture-audit-policy.md` (Brain) + `tools/architecture_audit.py` (Produto) |
| III — Revisão arquitetural periódica + evolução contínua | Cadência trimestral, usando o relatório da auditoria como ponto de partida obrigatório; escopo mínimo (inventário, Crews, Tasks Celery, APIs, integrações, cadeia LLM, deprecados, ADR-0013). Auditoria evolui conforme padrões recorrentes surgirem — não é lista fechada. | `knowledge/process/architecture-audit-policy.md` (Brain) |

Bloqueio de merge por achado Crítico fica para depois de um período de estabilização — decisão de produto futura, não desta ordem.

## 2. Severidade aplicada às 5 checagens existentes

| Categoria | Severidade | Por quê |
|---|---|---|
| `crew-sem-classificacao` | Crítico | "Crew sem classificação institucional" (exemplo literal da ordem) |
| `crew-fora-do-inventario-brain` | Crítico | "capacidade fora do inventário" |
| `crew-documentada-inexistente` | Crítico | Brain referencia Crew que não existe no código — documentação inconsistente |
| `router-documentado-inexistente` | Crítico | `CLAUDE.md` referencia router inexistente — referência quebrada |
| `task-nao-registrada` | Alto | "Task Celery sem registro" (exemplo literal) |
| `router-fora-da-doc` | Alto | "router não documentado" (exemplo literal) |
| `celery-autodiscover-nao-encontrado` | Alto | estrutura esperada não encontrada — exige checagem manual, não é violação confirmada |
| `claude-md-formato-inesperado` | Alto | idem — falha de introspecção, não achado confirmado |
| `ferramenta-orfa` | Médio | "ferramenta potencialmente órfã" (exemplo literal) |

Rodada atual (2026-07-17): 1 achado, `task-nao-registrada` (Alto) — `task_f_security_audit` fora do autodiscover, mesma pendência conhecida já registrada nos dois relatórios anteriores.

## 3. Verificação

- `python ../tools/architecture_audit.py` (local, venv ativo) — relatório com severidade, breakdown "(1 Alto)" no resultado final
- Mesma rodada com `GITHUB_ACTIONS=true` — confirma emissão de anotação `::warning::` para o achado Alto
- `ruff check app/ tests/ ../tools/` — limpo
- `npx pyright@1.1.386 tools/architecture_audit.py` — 0 erros
- `.github/workflows/ci.yml` — YAML validado (`yaml.safe_load`)
- Brain: `python3 tools/lint_brain.py` — 0 erros (1 aviso pré-existente, `jsonschema` não instalado) · `python3 tools/build_index.py` — índice ressincronizado

## Pendências conhecidas — fora do escopo desta ordem, registradas

1. **`task_f_security_audit` continua fora do `beat_schedule`/`autodiscover_tasks`** — terceira vez que este relatório registra a mesma pendência; falta decisão de frequência.
2. **Bloqueio de merge por Crítico** não está ativo — é evolução futura explícita da política, sem prazo definido.
3. **Revisão arquitetural trimestral** ainda não tem primeira data agendada — a política define cadência e escopo, não quando começa o primeiro ciclo.
