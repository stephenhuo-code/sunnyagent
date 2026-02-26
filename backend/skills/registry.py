"""Skill registry for global skill discovery.

Skills are internal resources used by agents to guide their behavior.
They are NOT user-invocable commands (use Commands for that).
"""

from dataclasses import dataclass, field
from pathlib import Path


# =============================================================================
# Skill Data Classes
# =============================================================================


@dataclass
class SkillEntry:
    """A registered skill with metadata and lazy-loaded instructions.

    Skills are atomic, single-agent resources that provide guidance for
    specific types of tasks. They are NOT user-invocable; users should
    use Commands (from commands/*.md) instead.
    """

    name: str  # Unique identifier (lowercase-hyphen)
    description: str  # Trigger condition description (from SKILL.md YAML)
    path: Path  # Directory containing SKILL.md
    source: str = "custom"  # Origin: "preset", "custom", "package:{agent}", "uploaded:{user_id}", "shared"
    _instructions: str | None = field(default=None, repr=False)

    def load_instructions(self) -> str:
        """Lazily load and cache the full SKILL.md content."""
        if self._instructions is None:
            self._instructions = (self.path / "SKILL.md").read_text()
        return self._instructions


# =============================================================================
# Registries
# =============================================================================

# Global skill registry (all skills)
SKILL_REGISTRY: dict[str, SkillEntry] = {}


# =============================================================================
# Registration Functions
# =============================================================================


def register_skill(entry: SkillEntry) -> None:
    """Register a skill in the global registry."""
    SKILL_REGISTRY[entry.name] = entry


def get_skill_summaries() -> str:
    """Return a formatted string of all skill names and descriptions.

    Note: Skills are internal resources, not user commands.
    This is used for agent context, not user display.
    """
    if not SKILL_REGISTRY:
        return "(No skills registered)"
    lines = [f"- {skill.name}: {skill.description}" for skill in SKILL_REGISTRY.values()]
    return "\n".join(lines)
