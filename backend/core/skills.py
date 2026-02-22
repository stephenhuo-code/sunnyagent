"""Agents and skills API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from backend.auth.dependencies import get_current_user
from backend.auth.models import UserInfo as User
from backend.plugins.database import get_disabled_plugin_names
from backend.registry import AGENT_REGISTRY
from backend.skills import SKILL_REGISTRY

router = APIRouter(tags=["agents & skills"])


def _is_skill_enabled(skill_source: str, disabled_plugins: set[str]) -> bool:
    """Check if a skill is enabled based on its source and disabled plugins.

    Args:
        skill_source: The skill source (e.g., "preset:research", "package:content-writer")
        disabled_plugins: Set of disabled plugin names for the user

    Returns:
        True if the skill is enabled (not in disabled list)
    """
    return skill_source not in disabled_plugins


@router.get("/api/agents")
async def list_agents(user: User = Depends(get_current_user)):
    """Return agents that should appear in the UI selector.

    Filters out agents from disabled plugins for the current user.
    """
    # Get user's disabled plugins
    disabled_plugins = await get_disabled_plugin_names(user.id)

    result = []
    for entry in AGENT_REGISTRY.values():
        if not entry.show_in_selector:
            continue

        # Check if agent is from a disabled plugin
        plugin_name = f"{entry.source}:{entry.name}"
        if plugin_name in disabled_plugins:
            continue

        result.append({
            "name": entry.name,
            "description": entry.description,
            "icon": entry.icon,
        })

    return result


@router.get("/api/skills")
async def list_skills(user: User = Depends(get_current_user)):
    """Return all registered skills (name + description only).

    Filters out skills from disabled plugins for the current user.
    """
    # Get user's disabled plugins
    disabled_plugins = await get_disabled_plugin_names(user.id)

    result = []
    for entry in SKILL_REGISTRY.values():
        # Check if skill is from a disabled plugin
        if not _is_skill_enabled(entry.source, disabled_plugins):
            continue

        result.append({
            "name": entry.name,
            "description": entry.description,
            "source": entry.source,
        })

    return result


@router.get("/api/skills/{name}")
async def get_skill(name: str, user: User = Depends(get_current_user)):
    """Return full skill details including instructions.

    Returns 404 if skill is disabled for the current user.
    """
    if name not in SKILL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Skill not found: {name}")

    entry = SKILL_REGISTRY[name]

    # Check if skill is from a disabled plugin
    disabled_plugins = await get_disabled_plugin_names(user.id)
    if not _is_skill_enabled(entry.source, disabled_plugins):
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{name}' is disabled for this user"
        )

    return {
        "name": entry.name,
        "description": entry.description,
        "instructions": entry.load_instructions(),
        "source": entry.source,
    }
