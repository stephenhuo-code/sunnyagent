"""Scan packages/ directory and register downloaded agent packages.

Each valid package directory must contain an AGENTS.md file.
Optionally it may contain a skills/ directory with skill subdirectories.

Package structure:
    packages/
        content-writer/
            AGENTS.md          # Agent memory / system prompt context
            skills/            # Optional skill definitions
                blog-post/
                    SKILL.md
                social-media/
                    SKILL.md

AGENTS.md frontmatter format (AIME extensions):
    ---
    name: content-writer
    description: Creates blog posts and social media content
    capabilities:
      - content_generation
      - writing
      - social_media
    ---
"""

import logging
import re
import threading
from pathlib import Path

import yaml

from backend.agents.package_agent import create_package_agent, create_package_tools
from backend.checkpointer_store import get_checkpointer
from backend.commands.loader import load_commands_from_directory
from backend.registry import register_agent
from backend.skills.loader import load_skills_from_directory

logger = logging.getLogger(__name__)

_PACKAGES_DIR = Path(__file__).resolve().parent.parent.parent / "packages"

# Track loaded packages to support hot-loading
_LOADED_PACKAGES: set[str] = set()
_LOAD_LOCK = threading.Lock()


def _parse_agents_md_frontmatter(agents_md: Path) -> dict[str, str | list[str]]:
    """Parse YAML frontmatter from AGENTS.md file.

    Returns dict with optional keys:
        - name: Agent name override
        - description: Agent description
        - capabilities: List of capability strings for AIME actor matching

    Returns empty dict if no frontmatter or parsing fails.
    """
    try:
        content = agents_md.read_text()
    except Exception as e:
        logger.warning(f"Failed to read {agents_md}: {e}")
        return {}

    # Extract YAML frontmatter between --- markers
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    try:
        metadata = yaml.safe_load(match.group(1))
        if not isinstance(metadata, dict):
            return {}

        result: dict[str, str | list[str]] = {}

        if "name" in metadata:
            result["name"] = str(metadata["name"])
        if "description" in metadata:
            result["description"] = str(metadata["description"])
        if "capabilities" in metadata and isinstance(metadata["capabilities"], list):
            result["capabilities"] = [str(c) for c in metadata["capabilities"]]

        return result
    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML in {agents_md}: {e}")
        return {}


def load_package_agents() -> None:
    """Scan packages/ and register a deep agent for each valid package.

    Called at startup. Records loaded packages in _LOADED_PACKAGES for
    subsequent hot-loading via scan_and_load_new_packages().
    """
    if not _PACKAGES_DIR.is_dir():
        logger.info("No packages/ directory found — skipping package loading")
        return

    with _LOAD_LOCK:
        for pkg_dir in sorted(_PACKAGES_DIR.iterdir()):
            if not pkg_dir.is_dir():
                continue

            agents_md = pkg_dir / "AGENTS.md"
            if not agents_md.exists():
                logger.warning("Skipping %s — no AGENTS.md found", pkg_dir.name)
                continue

            # Parse frontmatter to get the canonical name
            frontmatter = _parse_agents_md_frontmatter(agents_md)
            name = str(frontmatter.get("name", pkg_dir.name))

            _register_package(pkg_dir)
            _LOADED_PACKAGES.add(name)


def scan_and_load_new_packages() -> list[str]:
    """Scan packages/ directory and load newly discovered packages.

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

            agents_md = pkg_dir / "AGENTS.md"
            if not agents_md.exists():
                continue

            # Parse frontmatter to get the canonical name
            frontmatter = _parse_agents_md_frontmatter(agents_md)
            name = str(frontmatter.get("name", pkg_dir.name))

            # Skip already loaded packages
            if name in _LOADED_PACKAGES:
                continue

            # Load the new package
            _register_package(pkg_dir)
            _LOADED_PACKAGES.add(name)
            newly_loaded.append(name)
            logger.info(f"Hot-loaded new package: {name}")

    return newly_loaded


def _register_package(pkg_dir: Path) -> None:
    """Create a package agent from a package directory and register it.

    Uses custom create_package_agent instead of deepagents to have full
    control over the tool list (no automatic ls/filesystem browsing tools).
    """
    name = pkg_dir.name
    agents_md = pkg_dir / "AGENTS.md"

    # Parse YAML frontmatter for AIME metadata
    frontmatter = _parse_agents_md_frontmatter(agents_md)

    # Use frontmatter values with fallbacks
    agent_name = str(frontmatter.get("name", name))
    description = str(frontmatter.get("description", "")) or _extract_description(agents_md)
    capabilities: list[str] = []
    if "capabilities" in frontmatter:
        cap_value = frontmatter["capabilities"]
        if isinstance(cap_value, list):
            capabilities = cap_value

    # Build plugin name for commands and skills association
    plugin_name = f"package:{agent_name}"

    # Register package skills to global SKILL_REGISTRY
    skills_dir = pkg_dir / "skills"
    if skills_dir.is_dir():
        skill_count = load_skills_from_directory(skills_dir, source=plugin_name)
        logger.info(f"Registered {skill_count} skills from package '{agent_name}' to SKILL_REGISTRY")

    # Register package commands to global COMMAND_REGISTRY
    commands_dir = pkg_dir / "commands"
    if commands_dir.is_dir():
        cmd_count = load_commands_from_directory(commands_dir, plugin_name)
        logger.info(f"Registered {cmd_count} commands from package '{agent_name}' to COMMAND_REGISTRY")

    # Load AGENTS.md content (replaces deepagents memory=["/AGENTS.md"])
    agents_md_content = agents_md.read_text()

    # Create tools for this package agent
    tools = create_package_tools(plugin_name)

    # Create agent using our custom factory (NOT deepagents)
    # This gives full control over the tool list - no automatic ls/filesystem tools
    agent = create_package_agent(
        name=agent_name,
        agents_md_content=agents_md_content,
        checkpointer=get_checkpointer(),
        tools=tools,
    )

    register_agent(
        name=agent_name,
        description=description,
        graph=agent,
        tools=tools,  # Pass tools for registry
        show_in_selector=False,
        capabilities=capabilities,
        source="package",
    )

    cap_info = f", capabilities={capabilities}" if capabilities else ""
    logger.info("Registered package agent '%s'%s", agent_name, cap_info)


def _extract_description(agents_md: Path) -> str:
    """Extract a short description from AGENTS.md.

    Uses the first heading as description, falling back to the filename.
    """
    try:
        for line in agents_md.read_text().splitlines():
            line = line.strip()
            if line.startswith("# "):
                title = line[2:].strip()
                return title
            if line and not line.startswith("#"):
                return line[:120]
    except Exception:
        pass
    return agents_md.parent.name
