"""Drop messages — tabela vestigial (#412, precedente #365/#397).

A migration 2026_02_16_0002 criou `conversations` + `messages` para o produto
de chat. A 2026_04_11_0010 descontinuou o chat e dropou `conversations` +
`chat_messages` (a tabela que o serviço de chat de fato usava), mas esqueceu
`messages` — que nunca foi consumida pelo `chat_messages` nem por nenhum model
ativo (`grep -rn "messages" app/models/` só encontra `support_messages`, tabela
homônima e não relacionada). Órfã desde então, sem nenhum escritor ou leitor.

Revision ID: 2026_09_09_0042
Revises: 2026_09_07_0041
"""

from alembic import op

revision = "2026_09_09_0042"
down_revision = "2026_09_07_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_messages_conversation")
    op.execute("DROP TABLE IF EXISTS messages")


def downgrade() -> None:
    # Recria a estrutura (vazia) para reversibilidade do schema — os dados não
    # retornam. `conversation_id` não referencia `conversations` (já dropada
    # em 2026_04_11_0010): manter a FK aqui reintroduziria uma dependência
    # morta que a própria tabela já não tinha função alguma para preservar.
    op.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL,
            role            VARCHAR(50) NOT NULL,
            content         TEXT NOT NULL,
            metadata        JSONB NOT NULL DEFAULT '{}',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_conversation
        ON messages (conversation_id)
    """)
