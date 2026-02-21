"""Shared checkpointer store for all agents.

This module provides a central place to store and retrieve the checkpointer,
allowing agents to access it during initialization.

Usage:
    # In main.py (before build_supervisor):
    from backend.checkpointer_store import set_checkpointer
    set_checkpointer(checkpointer)

    # In agents:
    from backend.checkpointer_store import get_checkpointer
    agent = create_deep_agent(..., checkpointer=get_checkpointer())
"""

from langgraph.checkpoint.base import BaseCheckpointSaver

_checkpointer: BaseCheckpointSaver | None = None


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


def clear_checkpointer() -> None:
    """Clear the global checkpointer (for cleanup/testing)."""
    global _checkpointer
    _checkpointer = None
