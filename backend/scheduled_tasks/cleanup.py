"""
Cleanup utilities for scheduled tasks.

Handles log retention, expired task cleanup, and user deletion hooks.
"""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from backend.scheduled_tasks import database as db
from backend.scheduled_tasks.script_manager import script_manager
from backend.scheduled_tasks import scheduler

logger = logging.getLogger(__name__)

# Configuration
LOG_RETENTION_DAYS = 90


async def cleanup_old_logs() -> int:
    """
    Clean up execution logs older than LOG_RETENTION_DAYS.

    This should be run periodically (e.g., daily) as a scheduled job.

    Returns:
        Number of executions cleaned up
    """
    logger.info(f"Starting log retention cleanup (older than {LOG_RETENTION_DAYS} days)")

    try:
        # Delete old execution records from database
        # Note: This also triggers log file cleanup via the script_manager
        deleted_count = await db.delete_old_executions(LOG_RETENTION_DAYS)

        # Additionally clean up any orphaned log files
        await script_manager.cleanup_old_logs(LOG_RETENTION_DAYS)

        logger.info(f"Log cleanup completed: {deleted_count} executions removed")
        return deleted_count

    except Exception as e:
        logger.error(f"Log cleanup failed: {e}")
        raise


async def cleanup_user_tasks(user_id: UUID) -> dict:
    """
    Clean up all scheduled tasks for a user.

    Called when a user is deleted to remove all their tasks,
    scripts, logs, and APScheduler jobs.

    Args:
        user_id: The user ID being deleted

    Returns:
        Dictionary with cleanup statistics
    """
    logger.info(f"Starting cleanup for user {user_id}")

    stats = {
        "tasks_deleted": 0,
        "jobs_removed": 0,
        "scripts_deleted": 0,
        "errors": [],
    }

    try:
        # Get all tasks for the user
        tasks = await db.get_tasks_by_user(user_id)

        for task in tasks:
            try:
                # Remove APScheduler job
                if task.apscheduler_job_id:
                    try:
                        await scheduler.remove_schedule(task.apscheduler_job_id)
                        stats["jobs_removed"] += 1
                    except Exception as e:
                        stats["errors"].append(f"Job removal failed for {task.id}: {e}")

                # Delete script file
                try:
                    await script_manager.delete_script(user_id, task.id)
                    stats["scripts_deleted"] += 1
                except Exception as e:
                    stats["errors"].append(f"Script deletion failed for {task.id}: {e}")

                # Delete task logs
                try:
                    await script_manager.delete_task_logs(user_id, task.id)
                except Exception as e:
                    stats["errors"].append(f"Log deletion failed for {task.id}: {e}")

                # Delete task from database (cascade deletes executions)
                await db.delete_scheduled_task(task.id)
                stats["tasks_deleted"] += 1

            except Exception as e:
                stats["errors"].append(f"Task cleanup failed for {task.id}: {e}")
                logger.error(f"Error cleaning up task {task.id}: {e}")

        # Clean up user directory
        try:
            await script_manager.delete_user_directory(user_id)
        except Exception as e:
            stats["errors"].append(f"User directory deletion failed: {e}")

        logger.info(
            f"User cleanup completed: {stats['tasks_deleted']} tasks, "
            f"{stats['jobs_removed']} jobs, {stats['scripts_deleted']} scripts"
        )

        return stats

    except Exception as e:
        logger.error(f"User cleanup failed for {user_id}: {e}")
        raise


async def cleanup_expired_tasks() -> int:
    """
    Mark expired tasks as completed and disable them.

    A task is expired if its expiry_date has passed.

    Returns:
        Number of tasks marked as expired
    """
    from backend.scheduled_tasks.models import TaskStatus

    logger.info("Starting expired task cleanup")

    try:
        # Get all enabled tasks with expiry dates
        from backend.db import get_pool

        pool = await get_pool()

        query = """
            UPDATE scheduled_tasks
            SET status = 'expired', enabled = false, updated_at = NOW()
            WHERE enabled = true
            AND expiry_date IS NOT NULL
            AND expiry_date < NOW()
            RETURNING id, apscheduler_job_id
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query)

        # Remove APScheduler jobs for expired tasks
        for row in rows:
            if row["apscheduler_job_id"]:
                try:
                    await scheduler.remove_schedule(row["apscheduler_job_id"])
                except Exception as e:
                    logger.warning(f"Failed to remove job for expired task {row['id']}: {e}")

        logger.info(f"Expired task cleanup completed: {len(rows)} tasks marked as expired")
        return len(rows)

    except Exception as e:
        logger.error(f"Expired task cleanup failed: {e}")
        raise


async def schedule_cleanup_jobs():
    """
    Schedule periodic cleanup jobs.

    This should be called during application startup.
    """
    from backend.scheduled_tasks.triggers import create_daily_trigger
    from apscheduler.triggers.cron import CronTrigger

    try:
        # Schedule daily log cleanup at 3:00 AM
        await scheduler.add_schedule(
            job_id="scheduled_tasks:log_cleanup",
            func=cleanup_old_logs,
            trigger=CronTrigger(hour=3, minute=0),
            args=(),
        )

        # Schedule hourly expired task check
        await scheduler.add_schedule(
            job_id="scheduled_tasks:expired_cleanup",
            func=cleanup_expired_tasks,
            trigger=CronTrigger(minute=0),  # Every hour at :00
            args=(),
        )

        logger.info("Cleanup jobs scheduled")

    except Exception as e:
        logger.warning(f"Failed to schedule cleanup jobs: {e}")
