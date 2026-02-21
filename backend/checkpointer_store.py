"""Shared checkpointer and history graph store.

Provides:
- Checkpointer storage for all agents
- History graph for message persistence (aget_state/aupdate_state)

Usage:
    # In main.py (during startup):
    from backend.checkpointer_store import set_checkpointer, build_history_graph, set_history_graph
    set_checkpointer(checkpointer)
    history_graph = build_history_graph(checkpointer)
    set_history_graph(history_graph)

    # In agents:
    from backend.checkpointer_store import get_checkpointer
    agent = create_deep_agent(..., checkpointer=get_checkpointer())

    # For message history:
    from backend.checkpointer_store import get_history_graph
    state = await get_history_graph().aget_state(config)
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

_checkpointer: BaseCheckpointSaver | None = None
_history_graph: CompiledStateGraph | None = None


def set_checkpointer(checkpointer: BaseCheckpointSaver) -> None:
    """Set the global checkpointer.

    Must be called before agents are created.
    """
    global _checkpointer
    _checkpointer = checkpointer


def get_checkpointer() -> BaseCheckpointSaver | None:
    """Get the global checkpointer.

    Returns None if not yet initialized.
    """
    return _checkpointer


def _noop_node(state: MessagesState) -> MessagesState:
    """No-op node that returns state unchanged."""
    return state


def build_history_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """Create minimal graph for checkpointer access.

    Used for:
    - aget_state(): Read message history
    - aupdate_state(): Save messages (AIME direct_reply)

    Args:
        checkpointer: Checkpointer for state persistence

    Returns:
        Compiled StateGraph with checkpointer attached
    """
    # Trigger agent registration
    import backend.agents  # noqa: F401

    builder = StateGraph(MessagesState)
    builder.add_node("noop", _noop_node)
    builder.add_edge(START, "noop")
    builder.add_edge("noop", END)
    return builder.compile(checkpointer=checkpointer)


def set_history_graph(graph: CompiledStateGraph) -> None:
    """Set the global history graph."""
    global _history_graph
    _history_graph = graph


def get_history_graph() -> CompiledStateGraph | None:
    """Get the global history graph for aget_state/aupdate_state."""
    return _history_graph


def clear_checkpointer() -> None:
    """Clear the global checkpointer and history graph (for cleanup/testing)."""
    global _checkpointer, _history_graph
    _checkpointer = None
    _history_graph = None
