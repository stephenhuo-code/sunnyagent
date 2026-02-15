"""Progress Manager Module Contracts

Defines interfaces for Progress Manager components.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .planner import ProgressItem, SubtaskSpec, TaskResult, TaskStatus

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ProgressEvent:
    """Event emitted when progress changes.

    Used for SSE event generation.

    Attributes:
        event_type: Type of progress event
        task_id: Related task ID
        data: Event payload
        timestamp: Event timestamp
    """

    event_type: str  # "task_added", "task_started", "task_completed", "task_failed"
    task_id: str
    data: dict[str, Any]
    timestamp: datetime


# =============================================================================
# Abstract Base Classes
# =============================================================================


class ProgressManagerProtocol(ABC):
    """Protocol for Progress Manager implementations.

    The Progress Manager:
    1. Tracks all subtask states
    2. Manages task dependencies
    3. Controls parallel execution limits
    4. Emits progress events for SSE
    """

    @property
    @abstractmethod
    def max_parallel_tasks(self) -> int:
        """Maximum number of parallel tasks (default: 3)."""
        ...

    @property
    @abstractmethod
    def max_retry_count(self) -> int:
        """Maximum retry attempts per task (default: 3)."""
        ...

    @abstractmethod
    def add_tasks(self, specs: list[SubtaskSpec]) -> None:
        """Add multiple tasks to progress list.

        Args:
            specs: List of subtask specifications
        """
        ...

    @abstractmethod
    def get_next_tasks(self) -> list[SubtaskSpec]:
        """Get tasks ready for execution.

        Returns tasks where:
        - Status is 'pending'
        - All dependencies are 'completed'
        - Parallel limit not exceeded

        Returns:
            List of ready subtask specs (up to available slots)
        """
        ...

    @abstractmethod
    def start_task(self, task_id: str, agent: str) -> ProgressEvent:
        """Mark task as started.

        Args:
            task_id: Task identifier
            agent: Assigned agent name

        Returns:
            Progress event for SSE emission
        """
        ...

    @abstractmethod
    def complete_task(self, result: TaskResult) -> ProgressEvent:
        """Mark task as completed or failed.

        Args:
            result: Task execution result

        Returns:
            Progress event for SSE emission
        """
        ...

    @abstractmethod
    def should_retry(self, task_id: str) -> bool:
        """Check if task should be retried.

        Args:
            task_id: Task identifier

        Returns:
            True if retry count < max_retry_count
        """
        ...

    @abstractmethod
    def is_all_completed(self) -> bool:
        """Check if all tasks are completed.

        Returns:
            True if no pending or in_progress tasks remain
        """
        ...

    @abstractmethod
    def get_status(self, task_id: str) -> TaskStatus | None:
        """Get current status of a task.

        Args:
            task_id: Task identifier

        Returns:
            Task status or None if not found
        """
        ...

    @abstractmethod
    def get_results(self) -> dict[str, Any]:
        """Get all completed task results.

        Returns:
            Dictionary mapping task_id to result
        """
        ...

    @abstractmethod
    def to_todos(self) -> list[dict[str, str]]:
        """Convert progress to todos format for SSE.

        Returns:
            List of todo items with content and status
        """
        ...

    @abstractmethod
    def get_context_for_task(self, task_id: str) -> dict[str, Any]:
        """Get context data for a dependent task.

        Collects results from all completed dependencies.

        Args:
            task_id: Task identifier

        Returns:
            Context dictionary with dependency results
        """
        ...
