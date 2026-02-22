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
from pathlib import Path

import yaml
from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend

from backend.llm import get_model
from backend.registry import register_agent
from backend.checkpointer_store import get_checkpointer
from backend.skills.loader import load_skills_from_directory

logger = logging.getLogger(__name__)

_PACKAGES_DIR = Path(__file__).resolve().parent.parent.parent / "packages"


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
    """Scan packages/ and register a deep agent for each valid package."""
    if not _PACKAGES_DIR.is_dir():
        logger.info("No packages/ directory found — skipping package loading")
        return

    for pkg_dir in sorted(_PACKAGES_DIR.iterdir()):
        if not pkg_dir.is_dir():
            continue

        agents_md = pkg_dir / "AGENTS.md"
        if not agents_md.exists():
            logger.warning("Skipping %s — no AGENTS.md found", pkg_dir.name)
            continue

        _register_package(pkg_dir)


def _register_package(pkg_dir: Path) -> None:
    """Create a deep agent from a package directory and register it."""
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

    # Set up FilesystemBackend scoped to package directory
    backend = FilesystemBackend(root_dir=pkg_dir, virtual_mode=True)

    # Register package skills to global SKILL_REGISTRY (replaces deepagents SkillsMiddleware)
    skills_dir = pkg_dir / "skills"
    if skills_dir.is_dir():
        skill_count = load_skills_from_directory(skills_dir, source=f"package:{agent_name}")
        logger.info(f"Registered {skill_count} skills from package '{agent_name}' to SKILL_REGISTRY")

    # Don't pass skills to create_deep_agent - we use global SKILL_REGISTRY instead
    # Memory: always load AGENTS.md
    memory = ["/AGENTS.md"]

    # Use the package name as agent_name for model lookup, fallback to default
    model = get_model(agent_name)

    agent = create_deep_agent(
        model=model,
        backend=backend,
        skills=None,  # Use global SKILL_REGISTRY instead of deepagents SkillsMiddleware
        memory=memory,
        name=agent_name,
        checkpointer=get_checkpointer(),
    )

    register_agent(
        name=agent_name,
        description=description,
        graph=agent,
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
