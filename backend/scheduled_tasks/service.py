"""
Service layer for scheduled tasks.
"""

import logging
from datetime import datetime
from typing import Optional, List, Tuple
from uuid import UUID

from backend.scheduled_tasks.models import (
    ScheduledTask,
    ScheduledTaskWithScript,
    ScheduledTaskCreate,
    ScheduledTaskUpdate,
    TaskExecution,
    TaskExecutionDetail,
    ScheduleType,
    TaskStatus,
    ExecutionStatus,
    AdminScheduledTask,
)
from backend.scheduled_tasks import database as db
from backend.scheduled_tasks.script_manager import script_manager
from backend.scheduled_tasks.triggers import create_trigger
from backend.scheduled_tasks.validators import (
    validate_schedule_config,
    validate_expiry_date,
    validate_script_content,
    ValidationError,
)
from backend.scheduled_tasks import scheduler

logger = logging.getLogger(__name__)


class ScheduledTaskService:
    """Service for managing scheduled tasks."""

    # ============== Task CRUD Operations ==============

    async def create_task(
        self,
        user_id: UUID,
        data: ScheduledTaskCreate,
    ) -> ScheduledTask:
        """
        Create a new scheduled task.

        Args:
            user_id: The user ID
            data: Task creation data

        Returns:
            The created task

        Raises:
            ValidationError: If validation fails
        """
        # Validate script content
        validate_script_content(data.script_content)

        # Validate schedule config
        validated_config = validate_schedule_config(data.schedule_type, data.schedule_config)

        # Validate expiry date if provided
        if data.expiry_date:
            validate_expiry_date(data.expiry_date)

        # Create task record first to get ID
        task = await db.create_scheduled_task(
            user_id=user_id,
            title=data.title,
            schedule_type=data.schedule_type,
            schedule_config=validated_config,
            script_file_path="",  # Will be updated after creating script
            expiry_date=data.expiry_date,
        )

        # Create script file
        script_path = await script_manager.create_script(
            user_id=user_id,
            task_id=task.id,
            content=data.script_content,
        )

        # Create APScheduler job
        job_id = f"{user_id}:{task.id}"
        trigger = create_trigger(
            data.schedule_type,
            validated_config,
            data.expiry_date,
        )

        try:
            # Import executor function for APScheduler
            from backend.scheduled_tasks.executor import execute_scheduled_task

            await scheduler.add_schedule(
                job_id=job_id,
                func=execute_scheduled_task,
                trigger=trigger,
                args=(str(task.id),),
            )
        except Exception as e:
            logger.error(f"Failed to register APScheduler job: {e}")
            # Continue anyway, task can be run manually or job can be added later
            job_id = None

        # Update task with script path and job ID
        task = await db.update_scheduled_task(
            task_id=task.id,
            script_file_path=script_path,
            apscheduler_job_id=job_id,
        )

        # Get next run time
        if job_id:
            next_run = await scheduler.get_next_run_time(job_id)
            if next_run:
                task.next_run_time = next_run

        logger.info(f"Created scheduled task: {task.id} for user {user_id}")
        return task

    async def get_task(
        self,
        task_id: UUID,
        user_id: Optional[UUID] = None,
        include_script: bool = False,
    ) -> Optional[ScheduledTaskWithScript]:
        """
        Get a scheduled task by ID.

        Args:
            task_id: The task ID
            user_id: Optional user ID to filter by
            include_script: Whether to include script content

        Returns:
            The task or None if not found
        """
        task = await db.get_scheduled_task(task_id, user_id)
        if not task:
            return None

        # Convert to ScheduledTaskWithScript
        task_with_script = ScheduledTaskWithScript(
            **task.model_dump(),
            script_content=None,
        )

        # Get next run time
        if task.apscheduler_job_id:
            try:
                next_run = await scheduler.get_next_run_time(task.apscheduler_job_id)
                if next_run:
                    task_with_script.next_run_time = next_run
            except Exception:
                pass

        # Get last execution
        last_exec = await db.get_last_execution(task_id)
        if last_exec:
            task_with_script.last_run_time = last_exec.execution_time
            task_with_script.last_run_status = last_exec.status

        # Include script content if requested
        if include_script:
            content = await script_manager.read_script(
                user_id=task.user_id,
                task_id=task_id,
            )
            task_with_script.script_content = content

        return task_with_script

    async def list_tasks(
        self,
        user_id: UUID,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ScheduledTask], int]:
        """
        List scheduled tasks for a user.

        Args:
            user_id: The user ID
            status_filter: Optional status filter ('scheduled', 'completed', 'all')
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (tasks, total count)
        """
        tasks, total = await db.list_scheduled_tasks(
            user_id=user_id,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )

        # Enrich tasks with runtime info
        for task in tasks:
            if task.apscheduler_job_id:
                try:
                    next_run = await scheduler.get_next_run_time(task.apscheduler_job_id)
                    if next_run:
                        task.next_run_time = next_run
                except Exception:
                    pass

            # Get last execution
            last_exec = await db.get_last_execution(task.id)
            if last_exec:
                task.last_run_time = last_exec.execution_time
                task.last_run_status = last_exec.status

        return tasks, total

    async def update_task(
        self,
        task_id: UUID,
        user_id: UUID,
        data: ScheduledTaskUpdate,
    ) -> Optional[ScheduledTask]:
        """
        Update a scheduled task.

        Args:
            task_id: The task ID
            user_id: The user ID
            data: Update data

        Returns:
            The updated task or None if not found

        Raises:
            ValidationError: If validation fails
        """
        # Get existing task
        task = await db.get_scheduled_task(task_id, user_id)
        if not task:
            return None

        updates = {}

        # Validate and update fields
        if data.title is not None:
            updates["title"] = data.title

        if data.schedule_type is not None or data.schedule_config is not None:
            schedule_type = data.schedule_type or task.schedule_type
            schedule_config = data.schedule_config or task.schedule_config
            validated_config = validate_schedule_config(schedule_type, schedule_config)
            updates["schedule_type"] = schedule_type
            updates["schedule_config"] = validated_config

        if data.expiry_date is not None:
            validate_expiry_date(data.expiry_date)
            updates["expiry_date"] = data.expiry_date

        if data.script_content is not None:
            validate_script_content(data.script_content)
            await script_manager.update_script(
                user_id=user_id,
                task_id=task_id,
                content=data.script_content,
            )

        # Update database
        if updates:
            task = await db.update_scheduled_task(task_id, user_id, **updates)

        # Update APScheduler job if schedule changed
        if "schedule_type" in updates or "schedule_config" in updates or "expiry_date" in updates:
            await self._update_scheduler_job(task)

        logger.info(f"Updated scheduled task: {task_id}")
        return task

    async def delete_task(
        self,
        task_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Delete a scheduled task.

        Args:
            task_id: The task ID
            user_id: The user ID

        Returns:
            True if deleted, False if not found
        """
        # Get task first
        task = await db.get_scheduled_task(task_id, user_id)
        if not task:
            return False

        # Remove APScheduler job
        if task.apscheduler_job_id:
            await scheduler.remove_schedule(task.apscheduler_job_id)

        # Delete script file
        await script_manager.delete_script(user_id, task_id)

        # Delete task logs
        await script_manager.delete_task_logs(user_id, task_id)

        # Delete from database (cascades to executions)
        result = await db.delete_scheduled_task(task_id, user_id)

        logger.info(f"Deleted scheduled task: {task_id}")
        return result

    async def toggle_enabled(
        self,
        task_id: UUID,
        user_id: UUID,
        enabled: bool,
    ) -> Optional[ScheduledTask]:
        """
        Toggle task enabled state.

        Args:
            task_id: The task ID
            user_id: The user ID
            enabled: New enabled state

        Returns:
            The updated task or None if not found
        """
        task = await db.get_scheduled_task(task_id, user_id)
        if not task:
            return None

        # Update APScheduler
        if task.apscheduler_job_id:
            if enabled:
                await scheduler.resume_schedule(task.apscheduler_job_id)
            else:
                await scheduler.pause_schedule(task.apscheduler_job_id)

        # Update database
        task = await db.update_scheduled_task(task_id, user_id, enabled=enabled)

        logger.info(f"Toggled task {task_id} enabled={enabled}")
        return task

    async def run_now(
        self,
        task_id: UUID,
        user_id: UUID,
    ) -> Optional[TaskExecution]:
        """
        Run a task immediately.

        Args:
            task_id: The task ID
            user_id: The user ID

        Returns:
            The execution record or None if task not found
        """
        task = await db.get_scheduled_task(task_id, user_id)
        if not task:
            return None

        # Create execution record
        execution = await db.create_task_execution(
            task_id=task_id,
            execution_time=datetime.now(),
            status=ExecutionStatus.PENDING,
        )

        # Trigger immediate execution
        from backend.scheduled_tasks.executor import execute_scheduled_task_async

        # Run in background
        import asyncio
        asyncio.create_task(execute_scheduled_task_async(str(task_id), str(execution.id)))

        logger.info(f"Triggered immediate execution of task {task_id}")
        return execution

    # ============== Admin Operations ==============

    async def list_all_tasks(
        self,
        user_id_filter: Optional[UUID] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AdminScheduledTask], int]:
        """
        List all scheduled tasks (admin view).

        Args:
            user_id_filter: Optional user ID to filter by
            status_filter: Optional status filter
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (tasks, total count)
        """
        return await db.list_all_scheduled_tasks(
            user_id_filter=user_id_filter,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )

    # ============== Execution Operations ==============

    async def list_executions(
        self,
        task_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[TaskExecution], int]:
        """
        List executions for a task.

        Args:
            task_id: The task ID
            user_id: The user ID (for permission check)
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (executions, total count) or ([], 0) if task not found
        """
        # Verify task belongs to user
        task = await db.get_scheduled_task(task_id, user_id)
        if not task:
            return [], 0

        return await db.list_task_executions(task_id, page, page_size)

    async def get_execution_detail(
        self,
        task_id: UUID,
        execution_id: UUID,
        user_id: UUID,
    ) -> Optional[TaskExecutionDetail]:
        """
        Get execution detail with log content.

        Args:
            task_id: The task ID
            execution_id: The execution ID
            user_id: The user ID (for permission check)

        Returns:
            Execution detail or None if not found
        """
        # Verify task belongs to user
        task = await db.get_scheduled_task(task_id, user_id)
        if not task:
            return None

        execution = await db.get_task_execution(execution_id, task_id)
        if not execution:
            return None

        # Read log content
        log_content = None
        if execution.log_file_path:
            log_content = await script_manager.read_log(
                user_id=task.user_id,
                task_id=task_id,
                execution_id=execution_id,
            )

        return TaskExecutionDetail(
            **execution.model_dump(),
            log_content=log_content,
        )

    # ============== Helper Methods ==============

    async def _update_scheduler_job(self, task: ScheduledTask) -> None:
        """Update APScheduler job for a task."""
        if not task.apscheduler_job_id:
            return

        # Remove old job
        await scheduler.remove_schedule(task.apscheduler_job_id)

        # Create new job with updated config
        trigger = create_trigger(
            task.schedule_type,
            task.schedule_config,
            task.expiry_date,
        )

        from backend.scheduled_tasks.executor import execute_scheduled_task

        await scheduler.add_schedule(
            job_id=task.apscheduler_job_id,
            func=execute_scheduled_task,
            trigger=trigger,
            args=(str(task.id),),
        )

        # If task is disabled, pause the new job
        if not task.enabled:
            await scheduler.pause_schedule(task.apscheduler_job_id)


# Global service instance
scheduled_task_service = ScheduledTaskService()
