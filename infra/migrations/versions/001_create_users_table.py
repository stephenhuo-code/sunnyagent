"""Create users table

Revision ID: 001
Revises:
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE user_role AS ENUM ('admin', 'user')")
    op.execute("CREATE TYPE user_status AS ENUM ('active', 'disabled')")

    # Create users table
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            username VARCHAR(20) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role user_role NOT NULL DEFAULT 'user',
            status user_status NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Create indexes
    op.execute("CREATE UNIQUE INDEX idx_users_username_lower ON users(LOWER(username))")
    op.execute("CREATE INDEX idx_users_status ON users(status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS user_status")
    op.execute("DROP TYPE IF EXISTS user_role")
