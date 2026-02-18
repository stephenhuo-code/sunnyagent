"""Create projects and project_files tables, add project_id to conversations

Revision ID: 004
Revises: 003
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Create projects table
    op.execute("""
        CREATE TABLE projects (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)

    # Create indexes for projects
    op.execute("CREATE INDEX idx_projects_user ON projects(user_id) WHERE NOT is_deleted")
    op.execute("CREATE INDEX idx_projects_updated ON projects(updated_at DESC) WHERE NOT is_deleted")
    op.execute("CREATE UNIQUE INDEX uq_projects_user_name ON projects(user_id, name) WHERE NOT is_deleted")

    # Create trigger for updated_at (reuse existing function from 002 migration)
    op.execute("""
        CREATE TRIGGER projects_updated_at
            BEFORE UPDATE ON projects
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)

    # Step 2: Create project_files table
    op.execute("""
        CREATE TABLE project_files (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            file_id VARCHAR(36) NOT NULL,
            storage_path VARCHAR(512) NOT NULL,
            original_name VARCHAR(255) NOT NULL,
            content_type VARCHAR(100),
            size_bytes BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Create indexes for project_files
    op.execute("CREATE INDEX idx_project_files_project ON project_files(project_id)")
    op.execute("CREATE INDEX idx_project_files_file_id ON project_files(file_id)")
    op.execute("CREATE UNIQUE INDEX uq_project_files_project_name ON project_files(project_id, original_name)")

    # Step 3: Add project_id to conversations
    op.execute("ALTER TABLE conversations ADD COLUMN project_id UUID REFERENCES projects(id) ON DELETE SET NULL")
    op.execute("CREATE INDEX idx_conversations_project ON conversations(project_id) WHERE project_id IS NOT NULL AND NOT is_deleted")


def downgrade() -> None:
    # Remove project_id from conversations
    op.execute("DROP INDEX IF EXISTS idx_conversations_project")
    op.execute("ALTER TABLE conversations DROP COLUMN IF EXISTS project_id")

    # Drop project_files table
    op.execute("DROP TABLE IF EXISTS project_files")

    # Drop projects table
    op.execute("DROP TRIGGER IF EXISTS projects_updated_at ON projects")
    op.execute("DROP TABLE IF EXISTS projects")
