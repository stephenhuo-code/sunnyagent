"""Commands module for user-invocable /command system.

Commands are loaded from packages/*/commands/*.md files and can be
invoked by users using /command_name syntax.
"""

from backend.commands.registry import (
    COMMAND_REGISTRY,
    CommandEntry,
    register_command,
    get_commands_for_plugin,
    get_all_commands,
)
from backend.commands.loader import load_commands_from_directory

__all__ = [
    "COMMAND_REGISTRY",
    "CommandEntry",
    "register_command",
    "get_commands_for_plugin",
    "get_all_commands",
    "load_commands_from_directory",
]
