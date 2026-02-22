"""
API router for scheduled tasks.
"""

import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query

from backend.auth.dependencies import get_current_user, require_admin
from backend.auth.models import UserInfo
from backend.scheduled_tasks.models import (
    ScheduledTask,
    ScheduledTaskWithScript,
    ScheduledTaskCreate,
    ScheduledTaskUpdate,
    ScheduledTaskList,
    TaskExecution,
    TaskExecutionDetail,
    TaskExecutionList,
    AdminScheduledTaskList,
    ScheduledTasksSettings,
    UpdateScheduledTasksSettingsRequest,
)
from backend.scheduled_tasks.service import scheduled_task_service
from backend.scheduled_tasks.validators import ValidationError
from backend.scheduled_tasks import settings as task_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduled-tasks", tags=["scheduled-tasks"])
admin_router = APIRouter(prefix="/api/admin/scheduled-tasks", tags=["admin-scheduled-tasks"])


# ============== User Endpoints ==============


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    data: ScheduledTaskCreate,
    current_user: UserInfo = Depends(get_current_user),
) -> ScheduledTask:
    """
    Create a new scheduled task.

    Creates a task with the specified schedule configuration and script content.
    The script will be executed according to the schedule.
    """
    try:
        task = await scheduled_task_service.create_task(
            user_id=current_user.id,
            data=data,
        )
        return task
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "field": e.field},
        )


@router.get("")
async def list_tasks(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status: 'scheduled', 'completed', or 'all'",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserInfo = Depends(get_current_user),
) -> ScheduledTaskList:
    """
    List scheduled tasks for the current user.

    Supports filtering by status and pagination.
    """
    tasks, total = await scheduled_task_service.list_tasks(
        user_id=current_user.id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )
    return ScheduledTaskList(
        items=tasks,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}")
async def get_task(
    task_id: UUID,
    current_user: UserInfo = Depends(get_current_user),
) -> ScheduledTaskWithScript:
    """
    Get a scheduled task by ID.

    Returns the task with its script content.
    """
    task = await scheduled_task_service.get_task(
        task_id=task_id,
        user_id=current_user.id,
        include_script=True,
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


@router.patch("/{task_id}")
async def update_task(
    task_id: UUID,
    data: ScheduledTaskUpdate,
    current_user: UserInfo = Depends(get_current_user),
) -> ScheduledTask:
    """
    Update a scheduled task.

    Updates the specified fields of the task. If schedule configuration
    is changed, the APScheduler job will be updated accordingly.
    """
    try:
        task = await scheduled_task_service.update_task(
            task_id=task_id,
            user_id=current_user.id,
            data=data,
        )
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found",
            )
        return task
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "field": e.field},
        )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    current_user: UserInfo = Depends(get_current_user),
) -> None:
    """
    Delete a scheduled task.

    Removes the task, its script file, logs, and APScheduler job.
    """
    deleted = await scheduled_task_service.delete_task(
        task_id=task_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )


@router.post("/{task_id}/enable")
async def enable_task(
    task_id: UUID,
    current_user: UserInfo = Depends(get_current_user),
) -> ScheduledTask:
    """
    Enable a scheduled task.

    Resumes the APScheduler job for this task.
    """
    task = await scheduled_task_service.toggle_enabled(
        task_id=task_id,
        user_id=current_user.id,
        enabled=True,
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


@router.post("/{task_id}/disable")
async def disable_task(
    task_id: UUID,
    current_user: UserInfo = Depends(get_current_user),
) -> ScheduledTask:
    """
    Disable a scheduled task.

    Pauses the APScheduler job for this task.
    """
    task = await scheduled_task_service.toggle_enabled(
        task_id=task_id,
        user_id=current_user.id,
        enabled=False,
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


@router.post("/{task_id}/run")
async def run_task_now(
    task_id: UUID,
    current_user: UserInfo = Depends(get_current_user),
) -> TaskExecution:
    """
    Run a scheduled task immediately.

    Creates a new execution record and triggers the task execution
    in the background. Returns the execution record immediately.
    """
    execution = await scheduled_task_service.run_now(
        task_id=task_id,
        user_id=current_user.id,
    )
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return execution


# ============== Execution History Endpoints ==============


@router.get("/{task_id}/executions")
async def list_executions(
    task_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserInfo = Depends(get_current_user),
) -> TaskExecutionList:
    """
    List executions for a scheduled task.

    Returns paginated list of execution records, ordered by execution time (newest first).
    """
    executions, total = await scheduled_task_service.list_executions(
        task_id=task_id,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return TaskExecutionList(
        items=executions,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}/executions/{execution_id}")
async def get_execution_detail(
    task_id: UUID,
    execution_id: UUID,
    current_user: UserInfo = Depends(get_current_user),
) -> TaskExecutionDetail:
    """
    Get execution detail with log content.

    Returns the execution record with the full log content.
    """
    detail = await scheduled_task_service.get_execution_detail(
        task_id=task_id,
        execution_id=execution_id,
        user_id=current_user.id,
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )
    return detail


# ============== Admin Endpoints ==============


@admin_router.get("")
async def admin_list_tasks(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status: 'scheduled', 'completed', or 'all'",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    _: UserInfo = Depends(require_admin),
) -> AdminScheduledTaskList:
    """
    List all scheduled tasks (admin only).

    Supports filtering by user ID and status, with pagination.
    """
    tasks, total = await scheduled_task_service.list_all_tasks(
        user_id_filter=user_id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )
    return AdminScheduledTaskList(
        items=tasks,
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.get("/settings")
async def get_settings(
    _: UserInfo = Depends(require_admin),
) -> ScheduledTasksSettings:
    """
    Get global settings for scheduled tasks (admin only).

    Returns the current settings including global enabled status,
    max concurrent tasks, and default timeout.
    """
    settings = await task_settings.get_all_settings()
    return ScheduledTasksSettings(**settings)


@admin_router.patch("/settings")
async def update_settings(
    data: UpdateScheduledTasksSettingsRequest,
    _: UserInfo = Depends(require_admin),
) -> ScheduledTasksSettings:
    """
    Update global settings for scheduled tasks (admin only).

    Only the provided fields will be updated.
    """
    settings = await task_settings.update_settings(
        global_enabled=data.global_enabled,
        max_concurrent_tasks=data.max_concurrent_tasks,
        default_timeout_minutes=data.default_timeout_minutes,
    )
    return ScheduledTasksSettings(**settings)
