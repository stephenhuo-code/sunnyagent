"""Command registry for user-invocable /commands.

Commands are user-facing entry points that invoke specific workflows.
They are defined in packages/*/commands/*.md files.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CommandEntry:
    """A registered command with metadata and workflow content.

    Commands are user-invocable via /command_name syntax and execute
    a defined workflow using the associated agent.
    """

    name: str  # Command name (e.g., "analyze")
    description: str  # Short description for display
    argument_hint: str  # Argument hint (e.g., "<question>")
    path: Path  # Path to command .md file
    plugin_name: str  # Owning plugin (e.g., "package:data")
    _content: str | None = field(default=None, repr=False)

    def load_content(self) -> str:
        """Lazily load and cache the full command content (workflow)."""
        if self._content is None:
            self._content = self.path.read_text()
        return self._content


# Global command registry: command_name -> CommandEntry
COMMAND_REGISTRY: dict[str, CommandEntry] = {}


def register_command(entry: CommandEntry) -> None:
    """Register a command in the global registry."""
    COMMAND_REGISTRY[entry.name] = entry


def get_commands_for_plugin(plugin_name: str) -> list[CommandEntry]:
    """Get all commands belonging to a specific plugin.

    Args:
        plugin_name: Plugin name (e.g., "package:data")

    Returns:
        List of CommandEntry objects for this plugin
    """
    return [
        cmd for cmd in COMMAND_REGISTRY.values()
        if cmd.plugin_name == plugin_name
    ]


def get_all_commands() -> list[CommandEntry]:
    """Get all registered commands.

    Returns:
        List of all CommandEntry objects
    """
    return list(COMMAND_REGISTRY.values())
