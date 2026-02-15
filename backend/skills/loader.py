"""Loader for SKILL.md files from skills directories."""

import logging
import re
from pathlib import Path

import yaml

from backend.skills.registry import (
    SkillEntry,
    SkillStep,
    SkillType,
    WorkflowSkillInfo,
    register_skill,
    register_workflow_skill,
)

logger = logging.getLogger(__name__)

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def parse_skill_metadata(
    skill_md_path: Path,
) -> tuple[str | None, str | None, SkillType, list[SkillStep]]:
    """Parse YAML frontmatter from a SKILL.md file.

    Returns (name, description, skill_type, steps) or (None, None, "atomic", []) if parsing fails.

    YAML frontmatter format:
        ---
        name: skill-name
        description: Short description
        type: workflow  # Optional: "atomic" (default) or "workflow"
        steps:          # Optional: Only for workflow skills
          - id: step1
            description: First step description
            required_capability: web_search  # Optional
          - id: step2
            description: Second step description
        ---
    """
    try:
        content = skill_md_path.read_text()
    except Exception as e:
        logger.warning(f"Failed to read {skill_md_path}: {e}")
        return None, None, "atomic", []

    # Extract YAML frontmatter between --- markers
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        logger.warning(f"No YAML frontmatter in {skill_md_path}")
        return None, None, "atomic", []

    try:
        metadata = yaml.safe_load(match.group(1))
        name = metadata.get("name")
        description = metadata.get("description", "")
        if not name:
            logger.warning(f"No 'name' field in {skill_md_path}")
            return None, None, "atomic", []

        # Parse AIME extensions: type and steps
        skill_type: SkillType = metadata.get("type", "atomic")
        if skill_type not in ("atomic", "workflow"):
            logger.warning(f"Invalid skill type '{skill_type}' in {skill_md_path}, defaulting to 'atomic'")
            skill_type = "atomic"

        steps: list[SkillStep] = []
        raw_steps = metadata.get("steps", [])
        if isinstance(raw_steps, list):
            for step_data in raw_steps:
                if isinstance(step_data, dict) and "id" in step_data:
                    steps.append(
                        SkillStep(
                            id=step_data["id"],
                            description=step_data.get("description", ""),
                            required_capability=step_data.get("required_capability"),
                        )
                    )

        return name, description, skill_type, steps
    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML in {skill_md_path}: {e}")
        return None, None, "atomic", []


def load_skills_from_directory(skills_dir: Path) -> int:
    """Load all SKILL.md files from a directory.

    Returns the number of skills loaded.
    """
    if not skills_dir.exists():
        return 0

    count = 0
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        name, description, skill_type, steps = parse_skill_metadata(skill_md)
        if name:
            entry = SkillEntry(
                name=name,
                description=description or "",
                path=skill_dir,
                skill_type=skill_type,
            )
            register_skill(entry)
            logger.info(f"Registered skill: {name} (type={skill_type})")

            # Register workflow skill info for Planner use
            if skill_type == "workflow" and steps:
                workflow_info = WorkflowSkillInfo(name=name, steps=steps)
                register_workflow_skill(workflow_info)
                logger.info(f"Registered workflow skill steps for: {name} ({len(steps)} steps)")

            count += 1

    return count


def load_all_skills() -> int:
    """Load skills from all skill directories.

    Scans:
    - skills/anthropic/skills/ (git submodule from anthropics/skills)
    - skills/custom/ (project-specific skills)

    Returns total number of skills loaded.
    """
    total = 0
    skills_root = PROJECT_ROOT / "skills"

    # Load from anthropic skills (submodule has nested skills/ directory)
    anthropic_dir = skills_root / "anthropic" / "skills"
    count = load_skills_from_directory(anthropic_dir)
    if count:
        logger.info(f"Loaded {count} Anthropic skills from {anthropic_dir}")
    total += count

    # Load from custom skills
    custom_dir = skills_root / "custom"
    count = load_skills_from_directory(custom_dir)
    if count:
        logger.info(f"Loaded {count} custom skills from {custom_dir}")
    total += count

    logger.info(f"Total skills loaded: {total}")
    return total
