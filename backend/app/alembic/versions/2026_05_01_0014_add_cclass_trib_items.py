"""Add cclass_trib_items table.

Tabela de classificação tributária cClassTrib da LC 214.
Sincronizada semanalmente via Celery beat com a API SVRS.

Revision ID: 2026_05_01_0014
Revises: 2026_05_01_0013
Create Date: 2026-05-01
"""

from alembic import op

revision = "2026_05_01_0014"
down_revision = "2026_05_01_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS cclass_trib_items (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            codigo          TEXT NOT NULL UNIQUE,
            descricao       TEXT NOT NULL,
            p_cbs           NUMERIC(8,4) NOT NULL DEFAULT 0,
            p_ibs           NUMERIC(8,4) NOT NULL DEFAULT 0,
            regime_especial TEXT,
            vigencia_ini    DATE,
            vigencia_fim    DATE,
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            synced_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cclass_trib_codigo ON cclass_trib_items(codigo)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cclass_trib_active ON cclass_trib_items(is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cclass_trib_descricao ON cclass_trib_items USING gin(to_tsvector('portuguese', descricao))")

    # Seed inicial — códigos base da LC 214 para viabilizar testes antes da sincronização SVRS
    op.execute("""
        INSERT INTO cclass_trib_items (codigo, descricao, p_cbs, p_ibs, regime_especial, vigencia_ini) VALUES
        ('01.01.001', 'Animais vivos — bovinos', 0.0000, 0.0000, 'reducao_zero', '2026-01-01'),
        ('01.01.002', 'Animais vivos — suínos', 0.0000, 0.0000, 'reducao_zero', '2026-01-01'),
        ('02.01.001', 'Carnes e miudezas — bovino resfriado', 0.0000, 0.0000, 'reducao_zero', '2026-01-01'),
        ('02.01.002', 'Carnes e miudezas — bovino congelado', 0.0000, 0.0000, 'reducao_zero', '2026-01-01'),
        ('04.01.001', 'Leite e derivados — leite fluido', 0.0000, 0.0000, 'reducao_zero', '2026-01-01'),
        ('10.01.001', 'Cereais — arroz', 0.0000, 0.0000, 'reducao_zero', '2026-01-01'),
        ('10.01.002', 'Cereais — trigo', 0.0000, 0.0000, 'reducao_zero', '2026-01-01'),
        ('39.01.001', 'Plásticos e manufaturas — embalagens', 0.8800, 0.1760, NULL, '2026-01-01'),
        ('84.01.001', 'Máquinas e aparelhos — industriais', 0.8800, 0.1760, NULL, '2026-01-01'),
        ('84.01.002', 'Máquinas e aparelhos — agrícolas', 0.0000, 0.0000, 'reducao_zero', '2026-01-01'),
        ('85.01.001', 'Equipamentos elétricos — motores', 0.8800, 0.1760, NULL, '2026-01-01'),
        ('85.04.001', 'Transformadores e conversores', 0.8800, 0.1760, NULL, '2026-01-01'),
        ('99.01.001', 'Serviços gerais — tributação padrão', 0.9000, 0.1000, NULL, '2026-01-01'),
        ('99.01.002', 'Serviços de saúde', 0.0000, 0.0000, 'reducao_zero', '2026-01-01'),
        ('99.01.003', 'Serviços de educação', 0.0000, 0.0000, 'reducao_zero', '2026-01-01')
        ON CONFLICT (codigo) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cclass_trib_descricao")
    op.execute("DROP INDEX IF EXISTS idx_cclass_trib_active")
    op.execute("DROP INDEX IF EXISTS idx_cclass_trib_codigo")
    op.execute("DROP TABLE IF EXISTS cclass_trib_items")
