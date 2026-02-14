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
"""

import logging
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend

from backend.llm import get_model
from backend.registry import register_agent

logger = logging.getLogger(__name__)

_PACKAGES_DIR = Path(__file__).resolve().parent.parent.parent / "packages"


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

    # Extract description from AGENTS.md first line (# Title) or use name
    description = _extract_description(agents_md)

    # Set up FilesystemBackend scoped to package directory
    backend = FilesystemBackend(root_dir=pkg_dir, virtual_mode=True)

    # Determine skills sources (if skills/ directory exists)
    skills = None
    skills_dir = pkg_dir / "skills"
    if skills_dir.is_dir():
        skills = ["/skills/"]

    # Memory: always load AGENTS.md
    memory = ["/AGENTS.md"]

    # Use the package name as agent_name for model lookup, fallback to default
    model = get_model(name)

    agent = create_deep_agent(
        model=model,
        backend=backend,
        skills=skills,
        memory=memory,
        name=name,
    )

    register_agent(
        name=name,
        description=description,
        graph=agent,
        show_in_selector=False,
    )

    skill_count = len(list(skills_dir.iterdir())) if skills_dir.is_dir() else 0
    logger.info(
        "Registered package agent '%s' (%d skills)", name, skill_count
    )


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
