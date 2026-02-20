"""Create langfuse_user_mapping table for SunnyAgent-Langfuse user sync

Revision ID: 005
Revises: 004
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create langfuse_user_mapping table
    op.execute("""
        CREATE TABLE langfuse_user_mapping (
            id SERIAL PRIMARY KEY,
            sunnyagent_user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            langfuse_user_id VARCHAR(255) NOT NULL,
            langfuse_email VARCHAR(255) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Create index for Langfuse user ID lookup
    op.execute("CREATE INDEX idx_langfuse_user_mapping_langfuse_id ON langfuse_user_mapping(langfuse_user_id)")

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER langfuse_user_mapping_updated_at
            BEFORE UPDATE ON langfuse_user_mapping
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS langfuse_user_mapping_updated_at ON langfuse_user_mapping")
    op.execute("DROP TABLE IF EXISTS langfuse_user_mapping")
