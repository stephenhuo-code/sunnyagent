"""Dynamic Actors Package.

Contains actor implementations for task execution:
- Generic Actor: Fallback with sandbox, file_tools, activate_skill
- Specialized actors are loaded from the agent registry
"""

from backend.aime.actors.generic import create_generic_actor

__all__ = [
    "create_generic_actor",
]
