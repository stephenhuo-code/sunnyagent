"""Create conversations table

Revision ID: 002
Revises: 001
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create conversations table
    op.execute("""
        CREATE TABLE conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            thread_id VARCHAR(8) NOT NULL,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(50) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)

    # Create indexes
    op.execute("CREATE INDEX idx_conversations_user ON conversations(user_id) WHERE NOT is_deleted")
    op.execute("CREATE INDEX idx_conversations_updated ON conversations(updated_at DESC) WHERE NOT is_deleted")
    op.execute("CREATE INDEX idx_conversations_thread ON conversations(thread_id)")

    # Create trigger for updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER conversations_updated_at
            BEFORE UPDATE ON conversations
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS conversations_updated_at ON conversations")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at")
    op.execute("DROP TABLE IF EXISTS conversations")
