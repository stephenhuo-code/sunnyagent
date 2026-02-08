"""Skill registry for global skill discovery."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillEntry:
    """A registered skill with metadata and lazy-loaded instructions."""

    name: str  # Unique identifier (lowercase-hyphen)
    description: str  # Trigger condition description (from SKILL.md YAML)
    path: Path  # Directory containing SKILL.md
    _instructions: str | None = field(default=None, repr=False)

    def load_instructions(self) -> str:
        """Lazily load and cache the full SKILL.md content."""
        if self._instructions is None:
            self._instructions = (self.path / "SKILL.md").read_text()
        return self._instructions


# Global skill registry
SKILL_REGISTRY: dict[str, SkillEntry] = {}


def register_skill(entry: SkillEntry) -> None:
    """Register a skill in the global registry."""
    SKILL_REGISTRY[entry.name] = entry


def get_skill_summaries() -> str:
    """Return a formatted string of all skill names and descriptions."""
    if not SKILL_REGISTRY:
        return "(No skills registered)"
    lines = [f"- /{skill.name}: {skill.description}" for skill in SKILL_REGISTRY.values()]
    return "\n".join(lines)
