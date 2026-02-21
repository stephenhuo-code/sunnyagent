"""AIME (Autonomous Intent-driven Multi-agent Executor) Module.

Replaces the Supervisor + General Agent architecture with a dynamic
planning and execution system based on the AIME paper.

Public API:
- stream_aime_response(): Main entry point for chat
- get_aime_planner(): Get planner singleton

Core Components:
- IntentAnalyzer: Classifies user intent (direct_reply, delegate, plan, clarify)
- AIMEPlanner: Orchestrates task decomposition and execution
- ActorFactory: Selects and configures agents for subtasks
- ProgressManager: Tracks task state and emits SSE events
"""

from typing import Any, AsyncGenerator

from backend.aime.actor_factory import ActorFactory
from backend.aime.context import AgentContext
from backend.aime.intent import Action, IntentAnalyzer, IntentResult
from backend.aime.models import Actor, ProgressItem, ProgressList, SubtaskSpec, TaskStatus
from backend.aime.planner import AIMEPlanner
from backend.aime.progress_manager import ProgressManager

_planner: AIMEPlanner | None = None


def get_aime_planner() -> AIMEPlanner:
    """Get or create the AIME Planner singleton.

    Lazy initialization to avoid import cycles.

    Returns:
        AIMEPlanner instance
    """
    global _planner
    if _planner is None:
        import backend.agents  # noqa: F401  # Trigger agent registration
        _planner = AIMEPlanner()
    return _planner


async def stream_aime_response(
    thread_id: str,
    message: str,
    context: AgentContext | dict[str, Any] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream AIME response as SSE events.

    This is the main entry point for AIME-based chat processing.

    Args:
        thread_id: Conversation thread ID
        message: User message
        context: AgentContext or legacy dict (for backwards compatibility)

    Yields:
        SSE event dicts compatible with stream_handler.py format
    """
    planner = get_aime_planner()
    async for event in planner.process(
        message=message,
        thread_id=thread_id,
        context=context,
    ):
        yield event


__all__ = [
    # Public API
    "stream_aime_response",
    "get_aime_planner",
    # Intent
    "IntentAnalyzer",
    "IntentResult",
    "Action",
    # Models
    "SubtaskSpec",
    "ProgressItem",
    "ProgressList",
    "TaskStatus",
    "Actor",
    # Core Components
    "AIMEPlanner",
    "ActorFactory",
    "ProgressManager",
]
