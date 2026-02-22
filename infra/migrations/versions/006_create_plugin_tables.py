"""Create plugin management tables

Revision ID: 006
Revises: 005
Create Date: 2026-02-21

Creates 3 tables:
- uploaded_plugins: User-uploaded plugin records
- user_plugin_states: Per-user plugin enable/disable state
- plugin_ratings: Plugin rating records
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create uploaded_plugins table
    op.execute("""
        CREATE TABLE uploaded_plugins (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plugin_name VARCHAR(128) NOT NULL,
            plugin_type VARCHAR(16) NOT NULL CHECK (plugin_type IN ('agent', 'skill')),
            display_name VARCHAR(256) NOT NULL,
            description TEXT,
            version VARCHAR(32) DEFAULT '1.0.0',
            author VARCHAR(128),
            storage_path VARCHAR(512) NOT NULL,
            is_shared BOOLEAN DEFAULT FALSE,
            is_delisted BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id, plugin_name)
        )
    """)

    op.execute("CREATE INDEX idx_uploaded_plugins_user_id ON uploaded_plugins(user_id)")
    op.execute(
        "CREATE INDEX idx_uploaded_plugins_shared ON uploaded_plugins(is_shared, is_delisted)"
    )

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER uploaded_plugins_updated_at
            BEFORE UPDATE ON uploaded_plugins
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)

    # 2. Create user_plugin_states table
    op.execute("""
        CREATE TABLE user_plugin_states (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plugin_name VARCHAR(192) NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id, plugin_name)
        )
    """)

    op.execute(
        "CREATE INDEX idx_user_plugin_states_user_enabled ON user_plugin_states(user_id, enabled)"
    )

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER user_plugin_states_updated_at
            BEFORE UPDATE ON user_plugin_states
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)

    # 3. Create plugin_ratings table
    op.execute("""
        CREATE TABLE plugin_ratings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plugin_name VARCHAR(192) NOT NULL,
            rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id, plugin_name)
        )
    """)

    op.execute("CREATE INDEX idx_plugin_ratings_plugin ON plugin_ratings(plugin_name)")

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER plugin_ratings_updated_at
            BEFORE UPDATE ON plugin_ratings
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS plugin_ratings_updated_at ON plugin_ratings")
    op.execute("DROP TRIGGER IF EXISTS user_plugin_states_updated_at ON user_plugin_states")
    op.execute("DROP TRIGGER IF EXISTS uploaded_plugins_updated_at ON uploaded_plugins")

    # Drop tables in reverse order
    op.execute("DROP TABLE IF EXISTS plugin_ratings")
    op.execute("DROP TABLE IF EXISTS user_plugin_states")
    op.execute("DROP TABLE IF EXISTS uploaded_plugins")
