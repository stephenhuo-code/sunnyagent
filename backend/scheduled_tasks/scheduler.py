"""
APScheduler initialization and management.

Uses APScheduler 4.x with SQLAlchemyDataStore for PostgreSQL persistence.
"""

import logging
from typing import Optional, Callable, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from apscheduler import AsyncScheduler, CoalescePolicy, ConflictPolicy
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[AsyncScheduler] = None
_engine: Optional[AsyncEngine] = None

# Configuration constants
MAX_CONCURRENT_JOBS = 5


async def init_scheduler(database_url: str) -> AsyncScheduler:
    """
    Initialize the APScheduler with PostgreSQL persistence.

    Args:
        database_url: PostgreSQL connection string (asyncpg format)

    Returns:
        Configured AsyncScheduler instance
    """
    global _scheduler, _engine

    if _scheduler is not None:
        logger.warning("Scheduler already initialized, returning existing instance")
        return _scheduler

    # Convert database URL to asyncpg format if needed
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif not database_url.startswith("postgresql+asyncpg://"):
        database_url = f"postgresql+asyncpg://{database_url}"

    # Create async engine for APScheduler
    _engine = create_async_engine(database_url, echo=False)

    # Create data store with PostgreSQL
    data_store = SQLAlchemyDataStore(_engine)

    # Create scheduler with configuration
    _scheduler = AsyncScheduler(
        data_store=data_store,
        max_concurrent_jobs=MAX_CONCURRENT_JOBS,
    )

    logger.info(f"APScheduler initialized with max_concurrent_jobs={MAX_CONCURRENT_JOBS}")
    return _scheduler


async def start_scheduler() -> None:
    """Start the scheduler in background."""
    global _scheduler

    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler() first.")

    await _scheduler.start_in_background()
    logger.info("APScheduler started in background")


async def stop_scheduler() -> None:
    """Gracefully stop the scheduler."""
    global _scheduler, _engine

    if _scheduler is not None:
        await _scheduler.stop()
        logger.info("APScheduler stopped")
        _scheduler = None

    if _engine is not None:
        await _engine.dispose()
        _engine = None


def get_scheduler() -> AsyncScheduler:
    """
    Get the current scheduler instance.

    Returns:
        The active AsyncScheduler instance

    Raises:
        RuntimeError: If scheduler is not initialized
    """
    global _scheduler

    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler() first.")

    return _scheduler


async def add_schedule(
    job_id: str,
    func: Callable,
    trigger: DateTrigger | CronTrigger,
    args: Optional[tuple] = None,
    kwargs: Optional[dict] = None,
) -> str:
    """
    Add a new scheduled job.

    Args:
        job_id: Unique identifier for the job
        func: The function to execute
        trigger: APScheduler trigger (DateTrigger or CronTrigger)
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function

    Returns:
        The job ID
    """
    scheduler = get_scheduler()

    schedule = await scheduler.add_schedule(
        func,
        trigger=trigger,
        id=job_id,
        args=args or (),
        kwargs=kwargs or {},
        coalesce=CoalescePolicy.latest,
        conflict_policy=ConflictPolicy.replace,
        max_running_jobs=1,
    )

    logger.info(f"Added schedule: {job_id}")
    return job_id


async def remove_schedule(job_id: str) -> bool:
    """
    Remove a scheduled job.

    Args:
        job_id: The job ID to remove

    Returns:
        True if removed, False if not found
    """
    scheduler = get_scheduler()

    try:
        await scheduler.remove_schedule(job_id)
        logger.info(f"Removed schedule: {job_id}")
        return True
    except Exception as e:
        logger.warning(f"Failed to remove schedule {job_id}: {e}")
        return False


async def pause_schedule(job_id: str) -> bool:
    """
    Pause a scheduled job.

    Args:
        job_id: The job ID to pause

    Returns:
        True if paused, False if not found
    """
    scheduler = get_scheduler()

    try:
        await scheduler.pause_schedule(job_id)
        logger.info(f"Paused schedule: {job_id}")
        return True
    except Exception as e:
        logger.warning(f"Failed to pause schedule {job_id}: {e}")
        return False


async def resume_schedule(job_id: str) -> bool:
    """
    Resume a paused scheduled job.

    Args:
        job_id: The job ID to resume

    Returns:
        True if resumed, False if not found
    """
    scheduler = get_scheduler()

    try:
        await scheduler.resume_schedule(job_id)
        logger.info(f"Resumed schedule: {job_id}")
        return True
    except Exception as e:
        logger.warning(f"Failed to resume schedule {job_id}: {e}")
        return False


async def get_next_run_time(job_id: str) -> Optional[datetime]:
    """
    Get the next run time for a scheduled job.

    Args:
        job_id: The job ID

    Returns:
        The next run time or None if not found
    """
    scheduler = get_scheduler()

    try:
        schedules = await scheduler.get_schedules()
        for schedule in schedules:
            if schedule.id == job_id:
                return schedule.next_fire_time
        return None
    except Exception as e:
        logger.warning(f"Failed to get next run time for {job_id}: {e}")
        return None
