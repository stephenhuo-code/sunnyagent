"""Scan packages/ directory and register plugins.

Plugins are registered to PLUGIN_REGISTRY (metadata only).
Agent graphs are created dynamically by AIME ActorFactory at runtime.

Package structure:
    packages/
        data/
            .plugin/
                plugin.json    # Required: name, version, description, author
            skills/            # Optional skill definitions
                pdf/
                    SKILL.md
            commands/          # Optional command definitions
                analyze.md

plugin.json schema:
    {
        "name": "data",
        "version": "1.0.0",
        "description": "Data analysis plugin",
        "author": { "name": "Anthropic" },
        "keywords": ["data", "sql"],
        "capabilities": ["data_analysis", "sql", "visualization"]
    }
"""

import json
import logging
import threading
from pathlib import Path

from backend.commands.loader import load_commands_from_directory
from backend.plugins.registry import PluginEntry, register_plugin
from backend.skills.loader import load_skills_from_directory

logger = logging.getLogger(__name__)

_PACKAGES_DIR = Path(__file__).resolve().parent.parent.parent / "packages"
_LOADED_PACKAGES: set[str] = set()
_LOAD_LOCK = threading.Lock()


def _load_plugin_json(plugin_json_path: Path) -> dict | None:
    """Load and validate .plugin/plugin.json file.

    Args:
        plugin_json_path: Path to plugin.json file

    Returns:
        Parsed JSON dict or None if invalid
    """
    try:
        with open(plugin_json_path) as f:
            data = json.load(f)
        if not isinstance(data, dict) or "name" not in data:
            logger.warning(f"Invalid plugin.json: missing 'name' in {plugin_json_path}")
            return None
        return data
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in {plugin_json_path}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to read {plugin_json_path}: {e}")
        return None


def load_package_agents() -> None:
    """Scan packages/ and register plugins (metadata only).

    Called at startup. Records loaded packages in _LOADED_PACKAGES for
    subsequent hot-loading via scan_and_load_new_packages().

    Note: This function name is kept for backward compatibility but now
    registers to PLUGIN_REGISTRY instead of AGENT_REGISTRY.
    """
    if not _PACKAGES_DIR.is_dir():
        logger.info("No packages/ directory found")
        return

    with _LOAD_LOCK:
        for pkg_dir in sorted(_PACKAGES_DIR.iterdir()):
            if not pkg_dir.is_dir():
                continue

            plugin_json = pkg_dir / ".plugin" / "plugin.json"
            if not plugin_json.exists():
                logger.debug("Skipping %s — no .plugin/plugin.json", pkg_dir.name)
                continue

            plugin_data = _load_plugin_json(plugin_json)
            if plugin_data is None:
                continue

            name = plugin_data.get("name", pkg_dir.name)
            _register_plugin(pkg_dir, plugin_data)
            _LOADED_PACKAGES.add(name)


def scan_and_load_new_packages() -> list[str]:
    """Scan and load newly discovered packages.

    This enables hot-loading: packages added after startup are discovered
    and loaded when this function is called (e.g., when user opens plugin page).

    Returns:
        List of newly loaded package names.
    """
    if not _PACKAGES_DIR.is_dir():
        return []

    newly_loaded: list[str] = []
    with _LOAD_LOCK:
        for pkg_dir in sorted(_PACKAGES_DIR.iterdir()):
            if not pkg_dir.is_dir():
                continue

            plugin_json = pkg_dir / ".plugin" / "plugin.json"
            if not plugin_json.exists():
                continue

            plugin_data = _load_plugin_json(plugin_json)
            if plugin_data is None:
                continue

            name = plugin_data.get("name", pkg_dir.name)
            if name in _LOADED_PACKAGES:
                continue

            _register_plugin(pkg_dir, plugin_data)
            _LOADED_PACKAGES.add(name)
            newly_loaded.append(name)
            logger.info(f"Hot-loaded new plugin: {name}")

    return newly_loaded


def _register_plugin(pkg_dir: Path, plugin_data: dict) -> None:
    """Register a plugin (metadata only, no Agent creation).

    Args:
        pkg_dir: Package directory path
        plugin_data: Parsed plugin.json data
    """
    name = plugin_data.get("name", pkg_dir.name)
    description = plugin_data.get("description", "")
    version = plugin_data.get("version", "1.0.0")
    capabilities = plugin_data.get("capabilities", [])
    keywords = plugin_data.get("keywords", [])

    # Extract author name
    author = None
    author_data = plugin_data.get("author")
    if isinstance(author_data, dict):
        author = author_data.get("name")
    elif isinstance(author_data, str):
        author = author_data

    plugin_name = f"package:{name}"

    # Register skills to SKILL_REGISTRY
    skills_dir = pkg_dir / "skills"
    if skills_dir.is_dir():
        skill_count = load_skills_from_directory(skills_dir, source=plugin_name)
        logger.info(f"Registered {skill_count} skills from plugin '{name}'")

    # Register commands to COMMAND_REGISTRY
    commands_dir = pkg_dir / "commands"
    if commands_dir.is_dir():
        cmd_count = load_commands_from_directory(commands_dir, plugin_name)
        logger.info(f"[COMMANDS] Registered {cmd_count} commands from plugin '{name}' (plugin_name={plugin_name})")
    else:
        logger.warning(f"[COMMANDS] No commands directory found for plugin '{name}' at {commands_dir}")

    # Register plugin metadata (NO Agent creation)
    register_plugin(PluginEntry(
        name=name,
        description=description,
        path=pkg_dir,
        version=version,
        author=author,
        capabilities=capabilities,
        keywords=keywords,
        source="package",
    ))

    cap_info = f", capabilities={capabilities}" if capabilities else ""
    logger.info(f"Registered plugin '{name}'{cap_info}")
