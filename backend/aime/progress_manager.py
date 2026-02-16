"""Progress Manager - tracks task state and emits SSE events.

The Progress Manager maintains the global progress list and provides
methods for task state transitions. It integrates with the SSE event
system to notify the frontend of progress changes.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from backend.aime.models import ProgressItem, ProgressList, SubtaskSpec, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class ProgressEvent:
    """Event emitted when progress changes.

    Used for SSE event generation.
    """

    event_type: str  # "task_spawned", "task_completed", "todos_updated"
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class ProgressManager:
    """Manages task progress and emits SSE events.

    Wraps ProgressList with event emission capabilities.
    Thread-safe for concurrent task updates.
    """

    def __init__(self):
        """Initialize the Progress Manager."""
        self._progress = ProgressList()
        self._event_buffer: list[ProgressEvent] = []
        self._event_counter = 0
        logger.info("ProgressManager initialized")

    @property
    def progress(self) -> ProgressList:
        """Access the underlying progress list."""
        return self._progress

    def add_task(self, spec: SubtaskSpec) -> ProgressEvent:
        """Add a new task and emit task_spawned event.

        Args:
            spec: Subtask specification

        Returns:
            ProgressEvent for SSE emission
        """
        self._progress.add(spec)

        event = ProgressEvent(
            event_type="task_spawned",
            data={
                "task_id": spec.id,
                "description": spec.description,
                "capabilities": spec.capabilities,
                "depends_on": spec.depends_on,
            },
        )
        self._event_buffer.append(event)

        logger.debug(f"Task added: {spec.id} - {spec.description}")
        return event

    def start_task(self, task_id: str, agent_name: str) -> ProgressEvent | None:
        """Mark task as in progress and emit event.

        Args:
            task_id: Task identifier
            agent_name: Assigned agent name

        Returns:
            ProgressEvent or None if task not found
        """
        if task_id not in self._progress.items:
            logger.warning(f"Task not found: {task_id}")
            return None

        self._progress.mark_in_progress(task_id, agent_name)

        # Emit todos_updated with new status
        event = self._create_todos_updated_event()
        self._event_buffer.append(event)

        logger.info(f"[start_task] task:{task_id[:8]} → in_progress (agent={agent_name})")
        return event

    def complete_task(self, task_id: str, result: Any) -> ProgressEvent | None:
        """Mark task as completed and emit event.

        Args:
            task_id: Task identifier
            result: Task result

        Returns:
            ProgressEvent or None if task not found
        """
        if task_id not in self._progress.items:
            logger.warning(f"Task not found: {task_id}")
            return None

        self._progress.mark_completed(task_id, result)
        item = self._progress.items[task_id]

        # Emit task_completed event
        duration_ms = 0
        if item.started_at and item.completed_at:
            duration_ms = int((item.completed_at - item.started_at).total_seconds() * 1000)

        event = ProgressEvent(
            event_type="task_completed",
            data={
                "task_id": task_id,
                "status": "success",
                "duration_ms": duration_ms,
            },
        )
        self._event_buffer.append(event)

        result_preview = str(result)[:50] if result else "None"
        logger.info(
            f"[complete_task] task:{task_id[:8]} → completed "
            f"(duration_ms={duration_ms}, result='{result_preview}...')"
        )
        return event

    def fail_task(self, task_id: str, error: str) -> ProgressEvent | None:
        """Mark task as failed and emit event.

        Args:
            task_id: Task identifier
            error: Error message

        Returns:
            ProgressEvent or None if task not found
        """
        if task_id not in self._progress.items:
            logger.warning(f"Task not found: {task_id}")
            return None

        self._progress.mark_error(task_id, error)
        item = self._progress.items[task_id]

        # Emit task_completed event with error status
        event = ProgressEvent(
            event_type="task_completed",
            data={
                "task_id": task_id,
                "status": "error",
                "error": error,
                "retry_count": item.retry_count,
            },
        )
        self._event_buffer.append(event)

        logger.warning(
            f"[fail_task] task:{task_id[:8]} → error "
            f"(retry_count={item.retry_count}, error='{error[:50]}...')"
        )
        return event

    def should_retry(self, task_id: str, max_retries: int = 3) -> bool:
        """Check if task should be retried.

        Args:
            task_id: Task identifier
            max_retries: Maximum retry attempts

        Returns:
            True if retry count < max_retries
        """
        if task_id not in self._progress.items:
            return False

        item = self._progress.items[task_id]
        should = item.retry_count < max_retries
        logger.info(
            f"[should_retry] task:{task_id[:8]} → {should} "
            f"(retry_count={item.retry_count}, max={max_retries})"
        )
        return should

    def get_ready_tasks(self) -> list[SubtaskSpec]:
        """Get tasks ready for execution.

        Returns tasks where:
        - Status is 'pending'
        - All dependencies are 'completed'

        Returns:
            List of ready SubtaskSpecs
        """
        ready = self._progress.get_ready_tasks()
        logger.debug(f"[get_ready_tasks] Found {len(ready)} ready tasks")
        return ready

    def is_all_completed(self) -> bool:
        """Check if all tasks are completed.

        Returns:
            True if all tasks are in terminal state
        """
        return self._progress.is_all_completed()

    def get_results(self) -> dict[str, Any]:
        """Get all completed task results.

        Returns:
            Dict mapping task_id to result
        """
        return self._progress.get_results()

    def to_todos(self) -> list[dict[str, str]]:
        """Convert progress to todos format for SSE.

        Returns:
            List of todo items with content and status
        """
        return self._progress.to_todos()

    def drain_events(self) -> list[ProgressEvent]:
        """Drain and return buffered events.

        Returns:
            List of pending events (clears buffer)
        """
        events = self._event_buffer
        self._event_buffer = []
        return events

    def format_sse_event(self, event: ProgressEvent) -> dict[str, Any]:
        """Format ProgressEvent as SSE dict.

        Args:
            event: Progress event to format

        Returns:
            SSE-compatible dict
        """
        self._event_counter += 1
        return {
            "event": event.event_type,
            "data": json.dumps(event.data, ensure_ascii=False),
            "id": str(self._event_counter),
        }

    def _create_todos_updated_event(self) -> ProgressEvent:
        """Create a todos_updated event with current state.

        Returns:
            ProgressEvent with todos data
        """
        return ProgressEvent(
            event_type="todos_updated",
            data={
                "todos": self.to_todos(),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )
