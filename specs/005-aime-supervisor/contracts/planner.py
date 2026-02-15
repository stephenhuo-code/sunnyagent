"""Planner Module Contracts

Defines interfaces for AIME Planner components.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Literal

from .intent import IntentResult

# =============================================================================
# Type Definitions
# =============================================================================

TaskStatus = Literal["pending", "in_progress", "completed", "error", "cancelled"]


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SubtaskSpec:
    """Specification for a subtask, output by Planner.

    Passed to Actor Factory for agent selection and instantiation.

    Attributes:
        id: Unique task identifier (UUID)
        description: Human-readable task description
        skill_name: Optional skill name (indicates skill task)
        skill_step_id: Optional workflow skill step ID
        explicit_agent: User-specified agent (must be used if set)
        capabilities: Required capabilities for agent matching
        depends_on: List of task IDs that must complete first
        context: Context data from dependent tasks
    """

    id: str
    description: str
    skill_name: str | None = None
    skill_step_id: str | None = None
    explicit_agent: str | None = None
    capabilities: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    context: dict[str, Any] | None = None


@dataclass
class ProgressItem:
    """Progress status for a single task.

    Attributes:
        task_id: Task identifier
        description: Task description
        status: Current execution status
        result: Execution result (on completion)
        error: Error message (on failure)
        retry_count: Number of retry attempts
        started_at: Execution start time
        completed_at: Execution completion time
        assigned_agent: Agent assigned to this task
    """

    task_id: str
    description: str
    status: TaskStatus = "pending"
    result: Any = None
    error: str | None = None
    retry_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assigned_agent: str | None = None


@dataclass
class TaskResult:
    """Result returned by actor after task execution.

    Attributes:
        task_id: Task identifier
        status: Execution status
        output: Task output data
        error: Error message if failed
    """

    task_id: str
    status: Literal["success", "error"]
    output: Any = None
    error: str | None = None


# =============================================================================
# Abstract Base Classes
# =============================================================================


class ProgressListProtocol(ABC):
    """Protocol for progress list management.

    Maintains global task progress and handles state transitions.
    """

    @abstractmethod
    def add(self, spec: SubtaskSpec) -> None:
        """Add a new task to the progress list."""
        ...

    @abstractmethod
    def mark_in_progress(self, task_id: str, agent: str) -> None:
        """Mark task as started with assigned agent."""
        ...

    @abstractmethod
    def mark_completed(self, task_id: str, result: Any) -> None:
        """Mark task as successfully completed."""
        ...

    @abstractmethod
    def mark_error(self, task_id: str, error: str) -> None:
        """Mark task as failed with error message."""
        ...

    @abstractmethod
    def get_ready_tasks(self) -> list[SubtaskSpec]:
        """Get tasks ready for execution (dependencies satisfied)."""
        ...

    @abstractmethod
    def to_todos(self) -> list[dict[str, str]]:
        """Convert to todos format for SSE events."""
        ...


class PlannerProtocol(ABC):
    """Protocol for AIME Planner implementations.

    The Planner orchestrates the entire task lifecycle:
    1. Analyze intent
    2. Generate subtasks (for delegate/plan actions)
    3. Dispatch to Actor Factory
    4. Handle results and re-planning
    """

    @abstractmethod
    async def process(
        self,
        message: str,
        thread_id: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Process user message and yield SSE events.

        Args:
            message: User message
            thread_id: Conversation thread ID
            context: Optional conversation context

        Yields:
            SSE event dictionaries
        """
        ...

    @abstractmethod
    async def handle_task_result(self, result: TaskResult) -> None:
        """Handle result from actor execution.

        May trigger re-planning if task failed.

        Args:
            result: Task execution result
        """
        ...
