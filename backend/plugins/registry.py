"""Plugin registry for package plugins.

Plugins are loaded at startup and store metadata only.
Agent graphs are created dynamically at runtime by ActorFactory.

This separates the concept of:
- Agent: Pre-registered executable LangGraph graph (AGENT_REGISTRY)
- Plugin: Metadata from packages/ directory (PLUGIN_REGISTRY)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


PluginSource = Literal["package", "uploaded", "shared"]


@dataclass
class PluginEntry:
    """Plugin metadata - NOT an executable Agent.

    Plugin entries store metadata from plugin.json files.
    The actual Agent graph is created dynamically by ActorFactory
    when AIME routes a request to the plugin.

    Attributes:
        name: Plugin name from plugin.json
        description: Plugin description
        path: Package directory for dynamic agent creation
        version: Version string from plugin.json
        author: Author name from plugin.json
        capabilities: List of capabilities for AIME routing
        keywords: Search keywords
        source: Where the plugin came from (package, uploaded, shared)
    """

    name: str
    description: str
    path: Path  # Package directory for dynamic agent creation
    version: str = "1.0.0"
    author: str | None = None
    capabilities: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    source: PluginSource = "package"


# Global plugin registry - stores metadata only
PLUGIN_REGISTRY: dict[str, PluginEntry] = {}


def register_plugin(entry: PluginEntry) -> None:
    """Register a plugin to the registry.

    Args:
        entry: Plugin metadata entry
    """
    PLUGIN_REGISTRY[entry.name] = entry


def get_plugin(name: str) -> PluginEntry | None:
    """Get a plugin by name.

    Args:
        name: Plugin name

    Returns:
        PluginEntry or None if not found
    """
    return PLUGIN_REGISTRY.get(name)


def get_all_plugin_capabilities() -> list[tuple[str, str, list[str]]]:
    """Get (name, description, capabilities) for all plugins.

    Used by AIME for routing decisions.

    Returns:
        List of (name, description, capabilities) tuples
    """
    return [
        (entry.name, entry.description, entry.capabilities)
        for entry in PLUGIN_REGISTRY.values()
    ]
