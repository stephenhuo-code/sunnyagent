"""Agent registration system for the supervisor architecture."""

from dataclasses import dataclass, field

from langgraph.graph.state import CompiledStateGraph


@dataclass
class AgentEntry:
    """A registered agent with its metadata."""

    name: str
    description: str
    graph: CompiledStateGraph
    tools: list = field(default_factory=list)


AGENT_REGISTRY: dict[str, AgentEntry] = {}


def register_agent(
    name: str,
    description: str,
    graph: CompiledStateGraph,
    tools: list | None = None,
):
    """Register an agent so the supervisor and general agent can discover it."""
    AGENT_REGISTRY[name] = AgentEntry(
        name=name,
        description=description,
        graph=graph,
        tools=tools or [],
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
