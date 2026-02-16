"""AIME Contracts Package

This package defines the interfaces and data structures for the AIME architecture.
All implementations must conform to these contracts.

Modules:
    intent: Intent analysis interfaces (IntentAnalyzer, ClassifierBase)
    planner: Planner interfaces (PlannerProtocol, SubtaskSpec, ProgressItem)
    actor_factory: Actor Factory interfaces (ActorFactoryProtocol, Actor, AgentEntry)
    progress: Progress Manager interfaces (ProgressManagerProtocol, ProgressEvent)
"""

from .intent import (
    Action,
    ClassifierBase,
    DomainRecognizer,
    IntentAnalyzerProtocol,
    IntentResult,
)
from .planner import (
    PlannerProtocol,
    ProgressItem,
    ProgressListProtocol,
    SubtaskSpec,
    TaskResult,
    TaskStatus,
)
from .actor_factory import (
    Actor,
    ActorFactoryProtocol,
    AgentEntry,
    AgentSource,
    PRESET_CAPABILITIES,
)
from .progress import (
    ProgressEvent,
    ProgressManagerProtocol,
)

__all__ = [
    # Intent
    "Action",
    "IntentResult",
    "ClassifierBase",
    "DomainRecognizer",
    "IntentAnalyzerProtocol",
    # Planner
    "SubtaskSpec",
    "ProgressItem",
    "TaskResult",
    "TaskStatus",
    "ProgressListProtocol",
    "PlannerProtocol",
    # Actor Factory
    "Actor",
    "AgentEntry",
    "AgentSource",
    "ActorFactoryProtocol",
    "PRESET_CAPABILITIES",
    # Progress
    "ProgressEvent",
    "ProgressManagerProtocol",
]
