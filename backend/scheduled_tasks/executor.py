"""
Task executor for scheduled tasks.

Handles execution of scheduled tasks with timeout, retry logic,
and Langfuse tracing integration.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from backend.scheduled_tasks import database as db
from backend.scheduled_tasks.models import ExecutionStatus, TaskStatus
from backend.scheduled_tasks.script_manager import script_manager

logger = logging.getLogger(__name__)

# Configuration
EXECUTION_TIMEOUT_SECONDS = 15 * 60  # 15 minutes
RETRY_DELAY_SECONDS = 5 * 60  # 5 minutes
MAX_RETRIES = 1


async def execute_scheduled_task(task_id: str) -> None:
    """
    Execute a scheduled task (called by APScheduler).

    This is the entry point for APScheduler job execution.

    Args:
        task_id: The task ID as a string
    """
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        logger.error(f"Invalid task ID: {task_id}")
        return

    # Get task from database
    task = await db.get_scheduled_task(task_uuid)
    if not task:
        logger.warning(f"Task not found: {task_id}")
        return

    if not task.enabled:
        logger.info(f"Task {task_id} is disabled, skipping execution")
        return

    # Create execution record
    execution = await db.create_task_execution(
        task_id=task_uuid,
        execution_time=datetime.now(),
        status=ExecutionStatus.PENDING,
    )

    # Execute with retry logic
    await _execute_with_retry(task_uuid, execution.id, task.user_id)


async def execute_scheduled_task_async(task_id: str, execution_id: str) -> None:
    """
    Execute a scheduled task asynchronously (for "run now" feature).

    Args:
        task_id: The task ID as a string
        execution_id: The execution ID as a string
    """
    try:
        task_uuid = UUID(task_id)
        execution_uuid = UUID(execution_id)
    except ValueError:
        logger.error(f"Invalid task or execution ID: {task_id}, {execution_id}")
        return

    # Get task from database
    task = await db.get_scheduled_task(task_uuid)
    if not task:
        logger.warning(f"Task not found: {task_id}")
        return

    # Execute with retry logic
    await _execute_with_retry(task_uuid, execution_uuid, task.user_id)


async def _execute_with_retry(
    task_id: UUID,
    execution_id: UUID,
    user_id: UUID,
    retry_count: int = 0,
) -> None:
    """
    Execute a task with retry logic.

    Args:
        task_id: The task ID
        execution_id: The execution ID
        user_id: The user ID
        retry_count: Current retry count
    """
    start_time = datetime.now()
    log_content = []

    try:
        # Update execution status to running
        await db.update_task_execution(
            execution_id=execution_id,
            status=ExecutionStatus.RUNNING,
            retry_count=retry_count,
        )

        log_content.append(f"[{datetime.now().isoformat()}] 开始执行任务")

        # Read script content
        script_content = await script_manager.read_script(
            user_id=user_id,
            task_id=task_id,
        )

        if not script_content:
            raise ValueError("Script file not found or empty")

        log_content.append(f"[{datetime.now().isoformat()}] 脚本内容已加载")
        log_content.append(f"Prompt: {script_content[:200]}...")

        # Execute the task with timeout
        result = await asyncio.wait_for(
            _execute_aime_prompt(user_id, task_id, script_content, log_content),
            timeout=EXECUTION_TIMEOUT_SECONDS,
        )

        # Calculate duration
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        log_content.append(f"[{datetime.now().isoformat()}] 任务执行完成")
        log_content.append(f"结果: {result[:500] if result else 'No output'}...")

        # Write log file
        log_path = await script_manager.write_log(
            user_id=user_id,
            task_id=task_id,
            execution_id=execution_id,
            content="\n".join(log_content),
        )

        # Update execution as success
        await db.update_task_execution(
            execution_id=execution_id,
            status=ExecutionStatus.SUCCESS,
            duration_ms=duration_ms,
            log_file_path=log_path,
        )

        # Check if this is a one-time task
        task = await db.get_scheduled_task(task_id)
        if task and task.schedule_type.value == "once":
            await _complete_one_time_task(task_id)

        logger.info(f"Task {task_id} executed successfully in {duration_ms}ms")

    except asyncio.TimeoutError:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        log_content.append(f"[{datetime.now().isoformat()}] 任务执行超时")

        # Write log file
        log_path = await script_manager.write_log(
            user_id=user_id,
            task_id=task_id,
            execution_id=execution_id,
            content="\n".join(log_content),
        )

        # Update execution as timeout
        await db.update_task_execution(
            execution_id=execution_id,
            status=ExecutionStatus.TIMEOUT,
            duration_ms=duration_ms,
            log_file_path=log_path,
            error_message="Execution timed out after 15 minutes",
        )

        logger.warning(f"Task {task_id} timed out after {duration_ms}ms")

    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        error_message = str(e)
        log_content.append(f"[{datetime.now().isoformat()}] 任务执行失败: {error_message}")

        # Write log file
        log_path = await script_manager.write_log(
            user_id=user_id,
            task_id=task_id,
            execution_id=execution_id,
            content="\n".join(log_content),
        )

        # Check if we should retry
        if retry_count < MAX_RETRIES:
            logger.info(f"Task {task_id} failed, scheduling retry in {RETRY_DELAY_SECONDS}s")

            # Update execution with retry info
            await db.update_task_execution(
                execution_id=execution_id,
                status=ExecutionStatus.PENDING,
                duration_ms=duration_ms,
                log_file_path=log_path,
                error_message=f"Retry {retry_count + 1}: {error_message}",
                retry_count=retry_count + 1,
            )

            # Wait and retry
            await asyncio.sleep(RETRY_DELAY_SECONDS)
            await _execute_with_retry(task_id, execution_id, user_id, retry_count + 1)
        else:
            # Update execution as failed
            await db.update_task_execution(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                duration_ms=duration_ms,
                log_file_path=log_path,
                error_message=error_message,
            )

            logger.error(f"Task {task_id} failed after {retry_count + 1} attempts: {e}")


async def _execute_aime_prompt(
    user_id: UUID,
    task_id: UUID,
    prompt: str,
    log_content: list,
) -> str:
    """
    Execute the prompt using AIME.

    Args:
        user_id: The user ID
        task_id: The task ID
        prompt: The prompt to execute
        log_content: Log content list to append to

    Returns:
        The execution result as a string
    """
    # Import AIME components
    try:
        from backend.aime import get_aime_planner
        from backend.services.langfuse_service import get_langfuse_service
    except ImportError as e:
        log_content.append(f"[{datetime.now().isoformat()}] 无法加载 AIME: {e}")
        raise

    # Create Langfuse trace for observability
    langfuse_service = get_langfuse_service()
    trace = None

    if langfuse_service.enabled:
        try:
            trace = langfuse_service.langfuse.trace(
                name=f"scheduled_task:{task_id}",
                user_id=str(user_id),
                metadata={
                    "task_id": str(task_id),
                    "source": "scheduled_task",
                },
            )
            log_content.append(f"[{datetime.now().isoformat()}] Langfuse trace started")
        except Exception as e:
            log_content.append(f"[{datetime.now().isoformat()}] Langfuse trace failed: {e}")

    try:
        # Create a thread ID for this execution
        thread_id = f"scheduled_task_{task_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        log_content.append(f"[{datetime.now().isoformat()}] 创建 AIME planner")

        # Get AIME planner
        planner = get_aime_planner()

        log_content.append(f"[{datetime.now().isoformat()}] 执行 AIME 处理")

        # Collect results from stream
        results = []
        async for event in planner.stream(
            message=prompt,
            thread_id=thread_id,
            user_id=str(user_id),
        ):
            if hasattr(event, "content") and event.content:
                results.append(str(event.content))
            elif isinstance(event, dict) and event.get("content"):
                results.append(str(event["content"]))

        result = "\n".join(results) if results else "No output generated"

        log_content.append(f"[{datetime.now().isoformat()}] AIME 处理完成")

        if trace:
            trace.update(output=result[:1000])

        return result

    except Exception as e:
        log_content.append(f"[{datetime.now().isoformat()}] AIME 执行失败: {e}")
        if trace:
            trace.update(
                level="ERROR",
                status_message=str(e),
            )
        raise

    finally:
        if langfuse_service.enabled:
            try:
                langfuse_service.flush()
            except Exception:
                pass


async def _complete_one_time_task(task_id: UUID) -> None:
    """
    Mark a one-time task as completed after execution.

    Args:
        task_id: The task ID
    """
    try:
        await db.update_scheduled_task(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            enabled=False,
        )
        logger.info(f"One-time task {task_id} marked as completed")
    except Exception as e:
        logger.error(f"Failed to mark task {task_id} as completed: {e}")
