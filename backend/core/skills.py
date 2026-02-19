"""Agents and skills API endpoints."""

from fastapi import APIRouter, HTTPException

from backend.registry import AGENT_REGISTRY
from backend.skills import SKILL_REGISTRY

router = APIRouter(tags=["agents & skills"])


@router.get("/api/agents")
async def list_agents():
    """Return agents that should appear in the UI selector."""
    return [
        {"name": entry.name, "description": entry.description, "icon": entry.icon}
        for entry in AGENT_REGISTRY.values()
        if entry.show_in_selector
    ]


@router.get("/api/skills")
async def list_skills():
    """Return all registered skills (name + description only)."""
    return [
        {"name": entry.name, "description": entry.description}
        for entry in SKILL_REGISTRY.values()
    ]


@router.get("/api/skills/{name}")
async def get_skill(name: str):
    """Return full skill details including instructions."""
    if name not in SKILL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Skill not found: {name}")
    entry = SKILL_REGISTRY[name]
    return {
        "name": entry.name,
        "description": entry.description,
        "instructions": entry.load_instructions(),
    }
