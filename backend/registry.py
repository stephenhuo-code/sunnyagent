"""Agent registration system for the supervisor architecture."""

from dataclasses import dataclass, field
from typing import Literal

from langgraph.graph.state import CompiledStateGraph

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
# Agent Entry
# =============================================================================


@dataclass
class AgentEntry:
    """A registered agent with its metadata.

    Extended with capabilities and source for AIME actor selection.
    """

    name: str
    description: str
    graph: CompiledStateGraph
    tools: list = field(default_factory=list)
    icon: str = "bot"
    show_in_selector: bool = True
    # AIME extensions
    capabilities: list[str] = field(default_factory=list)
    source: AgentSource = "preset"


AGENT_REGISTRY: dict[str, AgentEntry] = {}


def register_agent(
    name: str,
    description: str,
    graph: CompiledStateGraph,
    tools: list | None = None,
    icon: str = "bot",
    show_in_selector: bool = True,
    capabilities: list[str] | None = None,
    source: AgentSource = "preset",
):
    """Register an agent so the supervisor and general agent can discover it.

    Args:
        name: Unique agent identifier
        description: Human-readable description
        graph: Compiled LangGraph for execution
        tools: Agent's tools
        icon: UI icon identifier
        show_in_selector: Whether to show in frontend selector
        capabilities: Declared capabilities for AIME actor matching
        source: Agent source (preset or package)
    """
    AGENT_REGISTRY[name] = AgentEntry(
        name=name,
        description=description,
        graph=graph,
        tools=tools or [],
        icon=icon,
        show_in_selector=show_in_selector,
        capabilities=capabilities or [],
        source=source,
    )


def get_agent_descriptions() -> str:
    """Return a formatted string of all registered agents for routing prompts."""
    return "\n".join(
        f"- **{e.name}**: {e.description}" for e in AGENT_REGISTRY.values()
    )


def get_all_tools() -> list:
    """Collect all unique tools from registered agents (for the general agent)."""
    seen: set[str] = set()
    tools = []
    for entry in AGENT_REGISTRY.values():
        for t in entry.tools:
            if t.name not in seen:
                seen.add(t.name)
                tools.append(t)
    return tools
