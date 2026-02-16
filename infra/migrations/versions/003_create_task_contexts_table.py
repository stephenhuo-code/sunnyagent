"""Create task_contexts table for AIME context management.

Revision ID: 003
Revises: 002
Create Date: 2026-02-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create task_contexts table with indexes."""
    op.create_table(
        "task_contexts",
        sa.Column("context_id", sa.String(64), primary_key=True),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("key_data", postgresql.JSONB(), nullable=True),
        sa.Column(
            "output_types",
            postgresql.ARRAY(sa.String()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "expected_output",
            postgresql.ARRAY(sa.String()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "last_accessed_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default="{}",
            nullable=False,
        ),
    )

    # Create indexes
    op.create_index(
        "idx_task_contexts_thread_id",
        "task_contexts",
        ["thread_id"],
    )
    op.create_index(
        "idx_task_contexts_expires_at",
        "task_contexts",
        ["expires_at"],
    )
    op.create_index(
        "idx_task_contexts_output_types",
        "task_contexts",
        ["output_types"],
        postgresql_using="gin",
    )

    # Add comments
    op.execute(
        "COMMENT ON TABLE task_contexts IS "
        "'AIME 任务上下文存储，支持滑动过期和 I/O 类型分类'"
    )
    op.execute(
        "COMMENT ON COLUMN task_contexts.output_types IS "
        "'自动分类的输出类型，如 [\"financial_report\", \"table\"]'"
    )
    op.execute(
        "COMMENT ON COLUMN task_contexts.expected_output IS "
        "'期望的输出类型，来自 SubtaskSpec 声明'"
    )


def downgrade() -> None:
    """Drop task_contexts table."""
    op.drop_index("idx_task_contexts_output_types", table_name="task_contexts")
    op.drop_index("idx_task_contexts_expires_at", table_name="task_contexts")
    op.drop_index("idx_task_contexts_thread_id", table_name="task_contexts")
    op.drop_table("task_contexts")
