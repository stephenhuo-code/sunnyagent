"""
Repository layer for scheduled tasks database operations.
"""

import logging
from datetime import datetime
from typing import Optional, List, Tuple
from uuid import UUID

from backend.db import get_pool
from backend.scheduled_tasks.models import (
    ScheduledTask,
    TaskExecution,
    ScheduleType,
    TaskStatus,
    ExecutionStatus,
    AdminScheduledTask,
)

logger = logging.getLogger(__name__)


# ============== Scheduled Tasks ==============

async def create_scheduled_task(
    user_id: UUID,
    title: str,
    schedule_type: ScheduleType,
    schedule_config: dict,
    script_file_path: str,
    expiry_date: Optional[datetime] = None,
    apscheduler_job_id: Optional[str] = None,
) -> ScheduledTask:
    """Create a new scheduled task."""
    pool = await get_pool()

    query = """
        INSERT INTO scheduled_tasks (
            user_id, title, schedule_type, schedule_config,
            script_file_path, expiry_date, apscheduler_job_id
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
    """

    import json
    config_json = json.dumps(schedule_config)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            query,
            user_id,
            title,
            schedule_type.value,
            config_json,
            script_file_path,
            expiry_date,
            apscheduler_job_id,
        )

    return _row_to_scheduled_task(row)


async def get_scheduled_task(task_id: UUID, user_id: Optional[UUID] = None) -> Optional[ScheduledTask]:
    """Get a scheduled task by ID, optionally filtered by user."""
    pool = await get_pool()

    if user_id:
        query = "SELECT * FROM scheduled_tasks WHERE id = $1 AND user_id = $2"
        args = (task_id, user_id)
    else:
        query = "SELECT * FROM scheduled_tasks WHERE id = $1"
        args = (task_id,)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)

    return _row_to_scheduled_task(row) if row else None


async def list_scheduled_tasks(
    user_id: UUID,
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[ScheduledTask], int]:
    """List scheduled tasks for a user with pagination."""
    pool = await get_pool()

    # Build query based on filter
    if status_filter == "scheduled":
        where_clause = "WHERE user_id = $1 AND status = 'scheduled'"
    elif status_filter == "completed":
        where_clause = "WHERE user_id = $1 AND status IN ('completed', 'expired')"
    else:
        where_clause = "WHERE user_id = $1"

    count_query = f"SELECT COUNT(*) FROM scheduled_tasks {where_clause}"
    list_query = f"""
        SELECT * FROM scheduled_tasks {where_clause}
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
    """

    offset = (page - 1) * page_size

    async with pool.acquire() as conn:
        total = await conn.fetchval(count_query, user_id)
        rows = await conn.fetch(list_query, user_id, page_size, offset)

    tasks = [_row_to_scheduled_task(row) for row in rows]
    return tasks, total


async def list_all_scheduled_tasks(
    user_id_filter: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[AdminScheduledTask], int]:
    """List all scheduled tasks for admin view."""
    pool = await get_pool()

    where_clauses = []
    args = []
    arg_idx = 1

    if user_id_filter:
        where_clauses.append(f"st.user_id = ${arg_idx}")
        args.append(user_id_filter)
        arg_idx += 1

    if status_filter == "scheduled":
        where_clauses.append("st.status = 'scheduled'")
    elif status_filter == "completed":
        where_clauses.append("st.status IN ('completed', 'expired')")

    where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    count_query = f"SELECT COUNT(*) FROM scheduled_tasks st {where_clause}"
    list_query = f"""
        SELECT st.*, u.username
        FROM scheduled_tasks st
        LEFT JOIN users u ON st.user_id = u.id
        {where_clause}
        ORDER BY st.created_at DESC
        LIMIT ${arg_idx} OFFSET ${arg_idx + 1}
    """

    offset = (page - 1) * page_size
    args.extend([page_size, offset])

    async with pool.acquire() as conn:
        total = await conn.fetchval(count_query, *args[:-2]) if args[:-2] else await conn.fetchval(count_query)
        rows = await conn.fetch(list_query, *args)

    tasks = [_row_to_admin_scheduled_task(row) for row in rows]
    return tasks, total


async def update_scheduled_task(
    task_id: UUID,
    user_id: Optional[UUID] = None,
    **updates,
) -> Optional[ScheduledTask]:
    """Update a scheduled task."""
    pool = await get_pool()

    # Build SET clause dynamically
    set_clauses = ["updated_at = NOW()"]
    args = []
    arg_idx = 1

    field_mapping = {
        "title": "title",
        "schedule_type": "schedule_type",
        "schedule_config": "schedule_config",
        "expiry_date": "expiry_date",
        "enabled": "enabled",
        "status": "status",
        "script_file_path": "script_file_path",
        "apscheduler_job_id": "apscheduler_job_id",
    }

    import json
    for key, db_field in field_mapping.items():
        if key in updates and updates[key] is not None:
            value = updates[key]
            if key == "schedule_type" and hasattr(value, "value"):
                value = value.value
            elif key == "status" and hasattr(value, "value"):
                value = value.value
            elif key == "schedule_config" and isinstance(value, dict):
                value = json.dumps(value)
            set_clauses.append(f"{db_field} = ${arg_idx}")
            args.append(value)
            arg_idx += 1

    if len(set_clauses) == 1:  # Only updated_at
        return await get_scheduled_task(task_id, user_id)

    # Build WHERE clause
    where_clause = f"id = ${arg_idx}"
    args.append(task_id)
    arg_idx += 1

    if user_id:
        where_clause += f" AND user_id = ${arg_idx}"
        args.append(user_id)

    query = f"""
        UPDATE scheduled_tasks
        SET {', '.join(set_clauses)}
        WHERE {where_clause}
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)

    return _row_to_scheduled_task(row) if row else None


async def delete_scheduled_task(task_id: UUID, user_id: Optional[UUID] = None) -> bool:
    """Delete a scheduled task."""
    pool = await get_pool()

    if user_id:
        query = "DELETE FROM scheduled_tasks WHERE id = $1 AND user_id = $2 RETURNING id"
        args = (task_id, user_id)
    else:
        query = "DELETE FROM scheduled_tasks WHERE id = $1 RETURNING id"
        args = (task_id,)

    async with pool.acquire() as conn:
        result = await conn.fetchval(query, *args)

    return result is not None


async def get_tasks_by_user(user_id: UUID) -> List[ScheduledTask]:
    """Get all tasks for a user (for cleanup)."""
    pool = await get_pool()

    query = "SELECT * FROM scheduled_tasks WHERE user_id = $1"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, user_id)

    return [_row_to_scheduled_task(row) for row in rows]


async def get_enabled_tasks() -> List[ScheduledTask]:
    """Get all enabled tasks (for scheduler recovery on startup)."""
    pool = await get_pool()

    query = "SELECT * FROM scheduled_tasks WHERE enabled = true AND status = 'scheduled'"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query)

    return [_row_to_scheduled_task(row) for row in rows]


# ============== Task Executions ==============

async def create_task_execution(
    task_id: UUID,
    execution_time: datetime,
    status: ExecutionStatus = ExecutionStatus.PENDING,
) -> TaskExecution:
    """Create a new task execution record."""
    pool = await get_pool()

    query = """
        INSERT INTO task_executions (task_id, execution_time, status)
        VALUES ($1, $2, $3)
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, task_id, execution_time, status.value)

    return _row_to_task_execution(row)


async def get_task_execution(execution_id: UUID, task_id: Optional[UUID] = None) -> Optional[TaskExecution]:
    """Get a task execution by ID."""
    pool = await get_pool()

    if task_id:
        query = "SELECT * FROM task_executions WHERE id = $1 AND task_id = $2"
        args = (execution_id, task_id)
    else:
        query = "SELECT * FROM task_executions WHERE id = $1"
        args = (execution_id,)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)

    return _row_to_task_execution(row) if row else None


async def list_task_executions(
    task_id: UUID,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[TaskExecution], int]:
    """List executions for a task with pagination."""
    pool = await get_pool()

    count_query = "SELECT COUNT(*) FROM task_executions WHERE task_id = $1"
    list_query = """
        SELECT * FROM task_executions
        WHERE task_id = $1
        ORDER BY execution_time DESC
        LIMIT $2 OFFSET $3
    """

    offset = (page - 1) * page_size

    async with pool.acquire() as conn:
        total = await conn.fetchval(count_query, task_id)
        rows = await conn.fetch(list_query, task_id, page_size, offset)

    executions = [_row_to_task_execution(row) for row in rows]
    return executions, total


async def update_task_execution(
    execution_id: UUID,
    **updates,
) -> Optional[TaskExecution]:
    """Update a task execution record."""
    pool = await get_pool()

    set_clauses = []
    args = []
    arg_idx = 1

    field_mapping = {
        "status": "status",
        "duration_ms": "duration_ms",
        "retry_count": "retry_count",
        "log_file_path": "log_file_path",
        "conversation_id": "conversation_id",
        "error_message": "error_message",
    }

    for key, db_field in field_mapping.items():
        if key in updates:
            value = updates[key]
            if key == "status" and hasattr(value, "value"):
                value = value.value
            set_clauses.append(f"{db_field} = ${arg_idx}")
            args.append(value)
            arg_idx += 1

    if not set_clauses:
        return await get_task_execution(execution_id)

    args.append(execution_id)

    query = f"""
        UPDATE task_executions
        SET {', '.join(set_clauses)}
        WHERE id = ${arg_idx}
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)

    return _row_to_task_execution(row) if row else None


async def get_last_execution(task_id: UUID) -> Optional[TaskExecution]:
    """Get the most recent execution for a task."""
    pool = await get_pool()

    query = """
        SELECT * FROM task_executions
        WHERE task_id = $1
        ORDER BY execution_time DESC
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, task_id)

    return _row_to_task_execution(row) if row else None


async def delete_old_executions(days: int = 90) -> int:
    """Delete executions older than specified days."""
    pool = await get_pool()

    query = """
        DELETE FROM task_executions
        WHERE created_at < NOW() - INTERVAL '$1 days'
        RETURNING id
    """

    async with pool.acquire() as conn:
        result = await conn.fetch(query.replace("$1", str(days)))

    return len(result)


# ============== Helper Functions ==============

def _row_to_scheduled_task(row) -> ScheduledTask:
    """Convert database row to ScheduledTask model."""
    import json

    config = row["schedule_config"]
    if isinstance(config, str):
        config = json.loads(config)

    return ScheduledTask(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        schedule_type=ScheduleType(row["schedule_type"]),
        schedule_config=config,
        expiry_date=row["expiry_date"],
        enabled=row["enabled"],
        status=TaskStatus(row["status"]),
        script_file_path=row["script_file_path"],
        apscheduler_job_id=row["apscheduler_job_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_admin_scheduled_task(row) -> AdminScheduledTask:
    """Convert database row to AdminScheduledTask model."""
    import json

    config = row["schedule_config"]
    if isinstance(config, str):
        config = json.loads(config)

    return AdminScheduledTask(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        schedule_type=ScheduleType(row["schedule_type"]),
        schedule_config=config,
        expiry_date=row["expiry_date"],
        enabled=row["enabled"],
        status=TaskStatus(row["status"]),
        script_file_path=row["script_file_path"],
        apscheduler_job_id=row["apscheduler_job_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        username=row.get("username"),
    )


def _row_to_task_execution(row) -> TaskExecution:
    """Convert database row to TaskExecution model."""
    return TaskExecution(
        id=row["id"],
        task_id=row["task_id"],
        execution_time=row["execution_time"],
        status=ExecutionStatus(row["status"]),
        duration_ms=row["duration_ms"],
        retry_count=row["retry_count"],
        log_file_path=row["log_file_path"],
        conversation_id=row["conversation_id"],
        error_message=row["error_message"],
        created_at=row["created_at"],
    )
