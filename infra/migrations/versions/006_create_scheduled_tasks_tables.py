"""Create scheduled_tasks and task_executions tables

Revision ID: 006
Revises: 005
Create Date: 2026-02-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create schedule_type enum
    schedule_type_enum = postgresql.ENUM(
        "once", "daily", "weekly", "monthly",
        name="schedule_type_enum",
        create_type=False
    )
    schedule_type_enum.create(op.get_bind(), checkfirst=True)

    # Create task_status enum
    task_status_enum = postgresql.ENUM(
        "scheduled", "completed", "expired", "error",
        name="task_status_enum",
        create_type=False
    )
    task_status_enum.create(op.get_bind(), checkfirst=True)

    # Create execution_status enum
    execution_status_enum = postgresql.ENUM(
        "pending", "running", "success", "failed", "timeout",
        name="execution_status_enum",
        create_type=False
    )
    execution_status_enum.create(op.get_bind(), checkfirst=True)

    # Create scheduled_tasks table
    op.create_table(
        "scheduled_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("schedule_type", schedule_type_enum, nullable=False),
        sa.Column("schedule_config", postgresql.JSONB, nullable=False),
        sa.Column("expiry_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("status", task_status_enum, server_default=sa.text("'scheduled'"), nullable=False),
        sa.Column("script_file_path", sa.String(500), nullable=False),
        sa.Column("apscheduler_job_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Create indexes for scheduled_tasks
    op.create_index("idx_scheduled_tasks_user_id", "scheduled_tasks", ["user_id"])
    op.create_index("idx_scheduled_tasks_status", "scheduled_tasks", ["status"])
    op.create_index("idx_scheduled_tasks_enabled", "scheduled_tasks", ["enabled"])

    # Create task_executions table
    op.create_table(
        "task_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scheduled_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("status", execution_status_enum, nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("retry_count", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("log_file_path", sa.String(500), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Create indexes for task_executions
    op.create_index("idx_task_executions_task_id", "task_executions", ["task_id"])
    op.create_index("idx_task_executions_execution_time", "task_executions", ["execution_time"])
    op.create_index("idx_task_executions_status", "task_executions", ["status"])


def downgrade() -> None:
    # Drop task_executions table and indexes
    op.drop_index("idx_task_executions_status", table_name="task_executions")
    op.drop_index("idx_task_executions_execution_time", table_name="task_executions")
    op.drop_index("idx_task_executions_task_id", table_name="task_executions")
    op.drop_table("task_executions")

    # Drop scheduled_tasks table and indexes
    op.drop_index("idx_scheduled_tasks_enabled", table_name="scheduled_tasks")
    op.drop_index("idx_scheduled_tasks_status", table_name="scheduled_tasks")
    op.drop_index("idx_scheduled_tasks_user_id", table_name="scheduled_tasks")
    op.drop_table("scheduled_tasks")

    # Drop enums
    execution_status_enum = postgresql.ENUM(name="execution_status_enum")
    execution_status_enum.drop(op.get_bind(), checkfirst=True)

    task_status_enum = postgresql.ENUM(name="task_status_enum")
    task_status_enum.drop(op.get_bind(), checkfirst=True)

    schedule_type_enum = postgresql.ENUM(name="schedule_type_enum")
    schedule_type_enum.drop(op.get_bind(), checkfirst=True)
