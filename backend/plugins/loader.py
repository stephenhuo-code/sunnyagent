"""Unified plugin loader for all sources (package, uploaded, shared).

All Agent sources use deepagents with unified loading:
- Package agents: Loaded at startup from packages/
- Uploaded agents: Loaded on upload by user
- Shared agents: Loaded when first enabled by a user

Skills are registered to global SKILL_REGISTRY instead of using
deepagents SkillsMiddleware for unified management.
"""

import logging
import re
from pathlib import Path
from uuid import UUID

import yaml
from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langgraph.graph.state import CompiledStateGraph

from backend.checkpointer_store import get_checkpointer
from backend.llm import get_model
from backend.plugins.models import PluginType
from backend.registry import register_agent
from backend.skills.loader import load_skills_from_directory

logger = logging.getLogger(__name__)


def parse_agents_md_frontmatter(agents_md: Path) -> dict[str, str | list[str]]:
    """Parse YAML frontmatter from AGENTS.md file.

    Returns dict with optional keys:
        - name: Agent name override
        - description: Agent description
        - version: Agent version
        - author: Agent author
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
        if "version" in metadata:
            result["version"] = str(metadata["version"])
        if "author" in metadata:
            result["author"] = str(metadata["author"])
        if "capabilities" in metadata and isinstance(metadata["capabilities"], list):
            result["capabilities"] = [str(c) for c in metadata["capabilities"]]

        return result
    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML in {agents_md}: {e}")
        return {}


def extract_description_from_agents_md(agents_md: Path) -> str:
    """Extract a short description from AGENTS.md.

    Uses the first heading as description, falling back to the filename.
    """
    try:
        for line in agents_md.read_text().splitlines():
            line = line.strip()
            if line.startswith("# "):
                title = line[2:].strip()
                return title
            if line and not line.startswith("#") and not line.startswith("---"):
                return line[:120]
    except Exception:
        pass
    return agents_md.parent.name


def load_agent_from_directory(
    pkg_dir: Path,
    source: str,
    user_id: UUID | None = None,
) -> tuple[str, CompiledStateGraph, dict[str, str | list[str]]]:
    """Load an agent from a directory structure.

    This is the unified loader for all agent sources:
    - Package: source="package", user_id=None
    - Uploaded: source="uploaded", user_id=<uploader_id>
    - Shared: source="shared", user_id=<original_uploader_id>

    Args:
        pkg_dir: Directory containing AGENTS.md and optional skills/
        source: Source type ("package", "uploaded", "shared")
        user_id: User ID for uploaded/shared agents

    Returns:
        Tuple of (agent_name, compiled_graph, metadata_dict)

    Raises:
        FileNotFoundError: If AGENTS.md doesn't exist
        ValueError: If AGENTS.md is invalid
    """
    agents_md = pkg_dir / "AGENTS.md"
    if not agents_md.exists():
        raise FileNotFoundError(f"AGENTS.md not found in {pkg_dir}")

    # Parse YAML frontmatter for AIME metadata
    frontmatter = parse_agents_md_frontmatter(agents_md)

    # Use frontmatter values with fallbacks
    agent_name = str(frontmatter.get("name", pkg_dir.name))
    description = str(frontmatter.get("description", "")) or extract_description_from_agents_md(
        agents_md
    )
    version = str(frontmatter.get("version", "1.0.0"))
    author = frontmatter.get("author")

    capabilities: list[str] = []
    if "capabilities" in frontmatter:
        cap_value = frontmatter["capabilities"]
        if isinstance(cap_value, list):
            capabilities = cap_value

    # Build source identifier for skills
    if source == "uploaded" and user_id:
        skill_source = f"uploaded:{user_id}"
    elif source == "shared":
        skill_source = "shared"
    else:
        skill_source = f"{source}:{agent_name}"

    # Register skills to global SKILL_REGISTRY
    skills_dir = pkg_dir / "skills"
    if skills_dir.is_dir():
        skill_count = load_skills_from_directory(skills_dir, source=skill_source)
        logger.info(f"Registered {skill_count} skills from {source} agent '{agent_name}'")

    # Set up FilesystemBackend scoped to package directory
    backend = FilesystemBackend(root_dir=pkg_dir, virtual_mode=True)

    # Memory: always load AGENTS.md
    memory = ["/AGENTS.md"]

    # Use the agent_name for model lookup, fallback to default
    model = get_model(agent_name)

    # Create deep agent without SkillsMiddleware (we use global SKILL_REGISTRY)
    agent = create_deep_agent(
        model=model,
        backend=backend,
        skills=None,
        memory=memory,
        name=agent_name,
        checkpointer=get_checkpointer(),
    )

    # Prepare metadata for return
    metadata = {
        "name": agent_name,
        "description": description,
        "version": version,
        "capabilities": capabilities,
    }
    if author:
        metadata["author"] = str(author)

    logger.info(
        f"Loaded {source} agent '{agent_name}' from {pkg_dir}"
        + (f" (capabilities={capabilities})" if capabilities else "")
    )

    return agent_name, agent, metadata


def detect_plugin_type(pkg_dir: Path) -> PluginType:
    """Detect whether a directory contains an agent or skill plugin.

    Args:
        pkg_dir: Directory to check

    Returns:
        PluginType.AGENT if AGENTS.md exists, else PluginType.SKILL
    """
    if (pkg_dir / "AGENTS.md").exists():
        return PluginType.AGENT
    elif (pkg_dir / "SKILL.md").exists():
        return PluginType.SKILL
    else:
        # Default to agent if structure is ambiguous
        raise ValueError(f"No AGENTS.md or SKILL.md found in {pkg_dir}")


def register_uploaded_agent(
    pkg_dir: Path,
    user_id: UUID,
    source: str = "uploaded",
) -> str:
    """Load and register an uploaded/shared agent to AGENT_REGISTRY.

    Args:
        pkg_dir: Directory containing AGENTS.md
        user_id: User ID of the uploader
        source: "uploaded" or "shared"

    Returns:
        The registered agent name
    """
    agent_name, agent, metadata = load_agent_from_directory(
        pkg_dir=pkg_dir,
        source=source,
        user_id=user_id,
    )

    # Register to AGENT_REGISTRY
    register_agent(
        name=agent_name,
        description=str(metadata.get("description", "")),
        graph=agent,
        show_in_selector=False,  # Uploaded agents not shown in global selector
        capabilities=metadata.get("capabilities", []),  # type: ignore
        source=source,  # type: ignore
    )

    return agent_name
