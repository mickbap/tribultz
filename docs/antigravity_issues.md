# Antigravity Issues – Inventário Rastreável

> Gerado em 2026-02-12T03:41 (branch `wip/antigravity-fixes`)
> Fonte: Pyre2 lint (IDE local). Todas são **"Could not find import"** porque os
> pacotes estão instalados apenas dentro do Docker, não no ambiente local.

## Status

- ☐ = pendente
- ☑ = resolvido

---

## Categoria A – Imports de pacotes pip (não instalados localmente)

| # | Arquivo | Linha | Mensagem | Status |
|---|---------|-------|----------|--------|
| 1 | `backend/app/config.py` | 3 | Could not find import of `pydantic_settings` | ☐ |
| 2 | `backend/app/database.py` | 3 | Could not find import of `sqlalchemy` | ☐ |
| 3 | `backend/app/database.py` | 4 | Could not find import of `sqlalchemy.orm` | ☐ |
| 4 | `backend/app/celery_app.py` | 3 | Could not find import of `celery` | ☐ |
| 5 | `backend/app/routers/audit.py` | 9 | Could not find import of `fastapi` | ☐ |
| 6 | `backend/app/routers/audit.py` | 10 | Could not find import of `pydantic` | ☐ |
| 7 | `backend/app/routers/audit.py` | 11 | Could not find import of `sqlalchemy` | ☐ |
| 8 | `backend/app/routers/audit.py` | 12 | Could not find import of `sqlalchemy.orm` | ☐ |
| 9 | `backend/app/routers/jobs.py` | 8 | Could not find import of `fastapi` | ☐ |
| 10 | `backend/app/routers/jobs.py` | 9 | Could not find import of `pydantic` | ☐ |
| 11 | `backend/app/routers/jobs.py` | 10 | Could not find import of `sqlalchemy` | ☐ |
| 12 | `backend/app/routers/jobs.py` | 11 | Could not find import of `sqlalchemy.orm` | ☐ |

## Categoria B – Imports de módulos internos (`app.*`)

| # | Arquivo | Linha | Mensagem | Status |
|---|---------|-------|----------|--------|
| 13 | `backend/app/database.py` | 6 | Could not find import of `app.config` | ☐ |
| 14 | `backend/app/celery_app.py` | 4 | Could not find import of `app.config` | ☐ |
| 15 | `backend/app/tasks/task_a_validate.py` | 9 | Could not find import of `app.celery_app` | ☐ |
| 16 | `backend/app/tasks/task_a_validate.py` | 10 | Could not find import of `app.tools.postgres_tool` | ☐ |

---

## Causa raiz

Todos os 16 erros têm a mesma causa:

> **Pyre2 roda no ambiente local (Windows) onde os pacotes pip não estão instalados.**
> O projeto foi desenhado para rodar exclusivamente dentro do Docker.

## Solução recomendada

1. **Criar venv local** com `pip install -r backend/requirements.txt` para que o
   Pyre2 encontre os pacotes pip (Categoria A).
2. **Configurar search roots** do Pyre2 para incluir `backend/` como raiz, assim
   os imports `app.*` (Categoria B) são resolvidos.
3. Alternativa: criar `pyrightconfig.json` ou `.pyre_configuration` na raiz com:
   ```json
   {
     "search_path": ["backend"],
     "source_directories": ["backend"]
   }
   ```
