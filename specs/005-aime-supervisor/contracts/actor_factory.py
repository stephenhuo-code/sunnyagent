"""Actor Factory Module Contracts

Defines interfaces for Actor Factory components.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from langgraph.graph.state import CompiledStateGraph

from .planner import SubtaskSpec

# =============================================================================
# Type Definitions
# =============================================================================

AgentSource = Literal["preset", "package"]
"""
Agent source types:
- preset: Built-in agents (research, sql, generic)
- package: Custom agents loaded from packages/ directory
"""


# =============================================================================
# Data Classes
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


@dataclass
class AgentEntry:
    """Registered agent metadata.

    Extended from existing registry structure with capability support.

    Attributes:
        name: Agent identifier
        description: Human-readable description
        graph: Compiled agent graph
        tools: Agent's tools
        icon: UI icon identifier
        show_in_selector: Whether to show in frontend selector
        capabilities: Declared capabilities for matching
        source: Agent source (preset or package)
    """

    name: str
    description: str
    graph: CompiledStateGraph
    tools: list[Any] = field(default_factory=list)
    icon: str = "bot"
    show_in_selector: bool = True
    capabilities: list[str] = field(default_factory=list)
    source: AgentSource = "preset"


# =============================================================================
# Abstract Base Classes
# =============================================================================


class ActorFactoryProtocol(ABC):
    """Protocol for Actor Factory implementations.

    The Actor Factory selects and instantiates actors based on subtask specs.
    Selection priority:
    1. Explicit agent specification (must use)
    2. Capability matching (preset and package agents compete)
    3. Default generic actor (fallback)
    """

    @abstractmethod
    def select_actor(self, spec: SubtaskSpec) -> Actor:
        """Select and instantiate actor for a subtask.

        Args:
            spec: Subtask specification from Planner

        Returns:
            Configured Actor ready for execution

        Raises:
            ValueError: If explicit_agent specified but not found
        """
        ...

    @abstractmethod
    def match_by_capabilities(
        self, required: list[str]
    ) -> tuple[AgentEntry, int] | None:
        """Find best matching agent by capabilities.

        Args:
            required: List of required capabilities

        Returns:
            Tuple of (matched entry, score) or None if no match
        """
        ...

    @abstractmethod
    def create_generic_actor(self, spec: SubtaskSpec) -> Actor:
        """Create a generic actor as fallback.

        Args:
            spec: Subtask specification

        Returns:
            Generic Actor with standard tools
        """
        ...


# =============================================================================
# Capability Constants
# =============================================================================

PRESET_CAPABILITIES: dict[str, list[str]] = {
    "research": ["web_search", "news_search", "academic_search"],
    "sql": ["database", "sql_query"],
    "generic": ["code_execution", "file_processing", "document_generation"],
}
"""Default capabilities for preset agents."""
