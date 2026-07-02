"""#409: Alembic é a fonte única do schema.

O schema.sql foi aposentado do bootstrap (compose) — logo TODA tabela usada
pelo código precisa nascer das migrations. Este teste roda contra o banco
migrado por `alembic upgrade head` (conftest local / step de CI) e trava o
retorno do drift: se um model novo ganhar tabela fora das migrations, falha.
"""

from __future__ import annotations

import os

import sqlalchemy as sa

# Tabelas que existiam apenas no schema.sql até #409 (models: feedback.py, support.py)
LEGACY_SCHEMA_SQL_TABLES = {"feedback", "known_errors", "support_tickets", "support_messages"}


def _inspector() -> sa.Inspector:
    engine = sa.create_engine(os.environ["DATABASE_URL"])
    return sa.inspect(engine)


def test_alembic_cria_tabelas_que_eram_so_do_schema_sql():
    insp = _inspector()
    missing = LEGACY_SCHEMA_SQL_TABLES - set(insp.get_table_names())
    assert not missing, (
        f"Tabelas usadas pelo código ausentes das migrations: {sorted(missing)}. "
        "O schema.sql foi aposentado (#409) — crie migration Alembic para elas."
    )


def test_todo_model_do_app_tem_tabela_migrada():
    """Anti-drift: cada __tablename__ dos models deve existir no banco migrado."""
    # Importar todos os models registra as tabelas no metadata do Base.
    import app.models  # noqa: F401
    from app.database import Base

    insp = _inspector()
    db_tables = set(insp.get_table_names())
    model_tables = set(Base.metadata.tables.keys())
    missing = model_tables - db_tables
    assert not missing, (
        f"Models com tabela fora das migrations: {sorted(missing)}. "
        "Alembic é a fonte única do schema (#409)."
    )
