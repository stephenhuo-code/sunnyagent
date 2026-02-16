"""AIME (Autonomous Intent-driven Multi-agent Executor) Module.

Replaces the Supervisor + General Agent architecture with a dynamic
planning and execution system based on the AIME paper.

Core Components:
- IntentAnalyzer: Classifies user intent (direct_reply, delegate, plan, clarify)
- AIMEPlanner: Orchestrates task decomposition and execution
- ActorFactory: Selects and configures agents for subtasks
- ProgressManager: Tracks task state and emits SSE events
"""

from backend.aime.actor_factory import ActorFactory
from backend.aime.intent import Action, IntentAnalyzer, IntentResult
from backend.aime.models import Actor, ProgressItem, ProgressList, SubtaskSpec, TaskStatus
from backend.aime.planner import AIMEPlanner
from backend.aime.progress_manager import ProgressManager

__all__ = [
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
