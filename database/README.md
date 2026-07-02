# Banco de dados — fonte única: Alembic

O schema do Tribultz é definido **exclusivamente** pelas migrations Alembic em
`backend/app/alembic/versions/` (#409). O antigo `schema.sql` foi aposentado em
02/07/2026 — ele divergia das migrations e fazia todo ambiente dev criado do
zero nascer quebrado (histórico preservado no git, se precisar consultar).

## Como o banco nasce

- **Dev (docker compose)**: o serviço one-shot `migrate` roda
  `alembic upgrade head` antes de `api`/`worker`/`beat` subirem
  (`infra/docker-compose.yml`). Volume zerado → banco completo, sem passo manual.
- **CI**: step "DB migrate (alembic)" antes do pytest (`.github/workflows/ci.yml`).
- **Testes locais**: `backend/conftest.py` sobe um testcontainer Postgres 16 e
  migra até head.
- **Produção**: `deploy.sh` com flag `migrate` (workflow Deploy Prod Magalu).

## Seeds

As migrations também criam os dados mínimos: tenant `default` (baseline),
planos de billing (0004/0006) e `tax_rules` 2026 (0005).

## Anti-drift

`backend/tests/test_schema_source_of_truth.py` falha se algum model do app
tiver `__tablename__` sem tabela correspondente no banco migrado — se você
criar um model novo, crie a migration junto.
