"""Skill registry for global skill discovery."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


# =============================================================================
# Type Definitions
# =============================================================================

SkillType = Literal["atomic", "workflow"]
"""
Skill types for AIME processing:
- atomic: Single agent completes the skill (default)
- workflow: Multi-step, may require multiple agents
"""


# =============================================================================
# Skill Data Classes
# =============================================================================


@dataclass
class SkillStep:
    """A single step in a Workflow Skill."""

    id: str  # Step identifier
    description: str  # Step description
    required_capability: str | None = None  # Capability needed for this step


@dataclass
class WorkflowSkillInfo:
    """Workflow Skill step definitions (used by Planner)."""

    name: str  # Skill name
    steps: list[SkillStep] = field(default_factory=list)


@dataclass
class SkillEntry:
    """A registered skill with metadata and lazy-loaded instructions."""

    name: str  # Unique identifier (lowercase-hyphen)
    description: str  # Trigger condition description (from SKILL.md YAML)
    path: Path  # Directory containing SKILL.md
    skill_type: SkillType = "atomic"  # AIME extension
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

# Workflow skills with step information (used by Planner)
WORKFLOW_SKILLS: dict[str, WorkflowSkillInfo] = {}


# =============================================================================
# Registration Functions
# =============================================================================


def register_skill(entry: SkillEntry) -> None:
    """Register a skill in the global registry."""
    SKILL_REGISTRY[entry.name] = entry


def register_workflow_skill(info: WorkflowSkillInfo) -> None:
    """Register a workflow skill's step information."""
    WORKFLOW_SKILLS[info.name] = info


def get_skill_summaries() -> str:
    """Return a formatted string of all skill names and descriptions."""
    if not SKILL_REGISTRY:
        return "(No skills registered)"
    lines = [f"- /{skill.name}: {skill.description}" for skill in SKILL_REGISTRY.values()]
    return "\n".join(lines)
