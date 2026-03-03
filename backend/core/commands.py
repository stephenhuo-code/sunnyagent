"""Commands API router for user-invocable /commands.

Returns commands from enabled plugins for the current user.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.auth.models import UserInfo
from backend.commands import COMMAND_REGISTRY
from backend.plugins.service import is_plugin_enabled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["commands"])


class CommandResponse(BaseModel):
    """Command response model."""

    name: str
    description: str
    argument_hint: str
    plugin_name: str


class CommandDetailResponse(BaseModel):
    """Detailed command response including content."""

    name: str
    description: str
    argument_hint: str
    plugin_name: str
    content: str  # Full markdown workflow content


@router.get("/commands", response_model=list[CommandResponse])
async def list_commands(user: UserInfo = Depends(get_current_user)) -> list[CommandResponse]:
    """Return all commands from enabled plugins for the current user.

    Commands are user-invocable via /command_name syntax in the input bar.
    Only returns commands from plugins that the user has enabled.
    """
    logger.info(f"[COMMANDS API] Total commands in registry: {len(COMMAND_REGISTRY)}")
    logger.info(f"[COMMANDS API] Commands: {list(COMMAND_REGISTRY.keys())}")

    result: list[CommandResponse] = []

    for cmd in COMMAND_REGISTRY.values():
        # Check if plugin is enabled for this user
        is_enabled = await is_plugin_enabled(user.id, cmd.plugin_name)
        logger.info(f"[COMMANDS API] Command '{cmd.name}' (plugin={cmd.plugin_name}) enabled={is_enabled}")
        if is_enabled:
            result.append(
                CommandResponse(
                    name=cmd.name,
                    description=cmd.description,
                    argument_hint=cmd.argument_hint,
                    plugin_name=cmd.plugin_name,
                )
            )

    # Sort by command name for consistent ordering
    result.sort(key=lambda c: c.name)

    logger.info(f"[COMMANDS API] Returning {len(result)} commands")
    return result


@router.get("/commands/{name}", response_model=CommandDetailResponse)
async def get_command_detail(
    name: str,
    user: UserInfo = Depends(get_current_user),
) -> CommandDetailResponse:
    """Get detailed info for a specific command including its content.

    Args:
        name: Command name (without the leading slash)
        user: Current authenticated user

    Returns:
        Full command details including workflow content

    Raises:
        HTTPException: 404 if command not found, 403 if plugin not enabled
    """
    if name not in COMMAND_REGISTRY:
        raise HTTPException(status_code=404, detail="Command not found")

    cmd = COMMAND_REGISTRY[name]

    # Check if user has access (plugin enabled)
    if not await is_plugin_enabled(user.id, cmd.plugin_name):
        raise HTTPException(status_code=403, detail="Plugin not enabled")

    return CommandDetailResponse(
        name=cmd.name,
        description=cmd.description,
        argument_hint=cmd.argument_hint,
        plugin_name=cmd.plugin_name,
        content=cmd.load_content(),
    )
