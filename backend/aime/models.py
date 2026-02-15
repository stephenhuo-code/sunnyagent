"""AIME Core Data Models.

Defines data structures for task specification and progress tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from langgraph.graph.state import CompiledStateGraph

# =============================================================================
# Type Definitions
# =============================================================================

TaskStatus = Literal["pending", "in_progress", "completed", "error", "cancelled"]
"""Status of a subtask in the progress list."""


# =============================================================================
# Subtask Specification
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

    id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    skill_name: str | None = None
    skill_step_id: str | None = None
    explicit_agent: str | None = None
    capabilities: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    context: dict[str, Any] | None = None


# =============================================================================
# Progress Tracking
# =============================================================================


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
class ProgressList:
    """Planner-maintained global progress list.

    Tracks all subtasks and their execution state.
    """

    items: dict[str, ProgressItem] = field(default_factory=dict)
    _subtask_specs: dict[str, SubtaskSpec] = field(default_factory=dict)

    def add(self, spec: SubtaskSpec) -> None:
        """Add a new task to the progress list."""
        self.items[spec.id] = ProgressItem(
            task_id=spec.id,
            description=spec.description,
        )
        self._subtask_specs[spec.id] = spec

    def mark_in_progress(self, task_id: str, agent: str) -> None:
        """Mark task as started with assigned agent."""
        if task_id in self.items:
            item = self.items[task_id]
            item.status = "in_progress"
            item.started_at = datetime.now()
            item.assigned_agent = agent

    def mark_completed(self, task_id: str, result: Any) -> None:
        """Mark task as successfully completed."""
        if task_id in self.items:
            item = self.items[task_id]
            item.status = "completed"
            item.completed_at = datetime.now()
            item.result = result

    def mark_error(self, task_id: str, error: str) -> None:
        """Mark task as failed with error message."""
        if task_id in self.items:
            item = self.items[task_id]
            item.status = "error"
            item.error = error
            item.retry_count += 1

    def mark_cancelled(self, task_id: str) -> None:
        """Mark task as cancelled."""
        if task_id in self.items:
            self.items[task_id].status = "cancelled"

    def get_spec(self, task_id: str) -> SubtaskSpec | None:
        """Get the SubtaskSpec for a task."""
        return self._subtask_specs.get(task_id)

    def get_ready_tasks(self) -> list[SubtaskSpec]:
        """Get tasks ready for execution (dependencies satisfied).

        Returns tasks where:
        - Status is 'pending'
        - All dependencies are 'completed'
        """
        ready = []
        for task_id, item in self.items.items():
            if item.status != "pending":
                continue
            spec = self._subtask_specs.get(task_id)
            if spec is None:
                continue
            # Check all dependencies are completed
            deps_satisfied = all(
                self.items.get(dep_id, ProgressItem(dep_id, "")).status == "completed"
                for dep_id in spec.depends_on
            )
            if deps_satisfied:
                ready.append(spec)
        return ready

    def is_all_completed(self) -> bool:
        """Check if all tasks are completed or cancelled."""
        return all(
            item.status in ("completed", "cancelled", "error")
            for item in self.items.values()
        )

    def get_results(self) -> dict[str, Any]:
        """Get all completed task results."""
        return {
            task_id: item.result
            for task_id, item in self.items.items()
            if item.status == "completed" and item.result is not None
        }

    def to_todos(self) -> list[dict[str, str]]:
        """Convert progress to todos format for SSE events.

        Returns:
            List of todo items with content and status
        """
        return [
            {
                "content": item.description,
                "status": (
                    "completed"
                    if item.status == "completed"
                    else "in_progress"
                    if item.status == "in_progress"
                    else "pending"
                ),
            }
            for item in self.items.values()
        ]


# =============================================================================
# Actor
# =============================================================================


@dataclass
class Actor:
    """Instantiated actor ready for execution.

    Attributes:
        name: Agent name
        graph: Compiled LangGraph for execution
        tools: Available tools
        persona: Optional role description from skill
    """

    name: str
    graph: CompiledStateGraph
    tools: list[Any] = field(default_factory=list)
    persona: str | None = None
