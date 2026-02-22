"""Plugin management API endpoints.

Provides REST API for:
- Listing plugins (GET /api/plugins)
- Plugin details (GET /api/plugins/{plugin_name})
- Enable/disable (PATCH /api/plugins/{plugin_name})
- Marketplace (GET /api/plugins/marketplace)
- Upload (POST /api/plugins/upload)
- Delete (DELETE /api/plugins/{plugin_name})
- Share/unshare (POST/DELETE /api/plugins/{plugin_name}/share)
- Rating (GET/PUT /api/plugins/{plugin_name}/rating)
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from backend.auth.dependencies import get_current_user
from backend.auth.models import UserInfo
from backend.plugins import database as plugin_db
from backend.plugins.models import (
    PluginInfo,
    PluginListResponse,
    PluginRatingInfo,
    PluginRatingRequest,
    PluginSource,
    PluginStateUpdateRequest,
    PluginType,
    PluginUploadResponse,
)
from backend.plugins.service import (
    delete_uploaded_plugin,
    get_all_plugins,
    get_marketplace_plugins,
    get_plugin,
    register_uploaded_plugin,
    update_plugin_state,
)
from backend.plugins.validator import validate_plugin_package, extract_plugin_package

logger = logging.getLogger(__name__)

# Directory for uploaded plugins
UPLOADED_PLUGINS_DIR = Path("uploaded_plugins")

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


# =============================================================================
# Plugin List Endpoints
# =============================================================================


@router.get("", response_model=PluginListResponse)
async def list_plugins(
    source: PluginSource | None = Query(None, description="Filter by source type"),
    type: PluginType | None = Query(None, description="Filter by plugin type"),
    enabled: bool | None = Query(None, description="Filter by enabled status"),
    search: str | None = Query(None, description="Search in name and description"),
    user: UserInfo = Depends(get_current_user),
) -> PluginListResponse:
    """List all plugins visible to the current user.

    Returns plugins from all sources:
    - Preset (built-in)
    - Package (from packages/ directory)
    - Uploaded (user's own uploads)
    - Shared (shared by other users)
    """
    plugins = await get_all_plugins(
        user_id=user.id,
        source_filter=source,
        type_filter=type,
        enabled_filter=enabled,
        search=search,
    )
    return PluginListResponse(plugins=plugins)


@router.get("/marketplace", response_model=PluginListResponse)
async def browse_marketplace(
    source: PluginSource | None = Query(None, description="Filter by source"),
    search: str | None = Query(None, description="Search query"),
    sort: str = Query("name", description="Sort order: name, rating, recent"),
    user: UserInfo = Depends(get_current_user),
) -> PluginListResponse:
    """Browse plugin marketplace.

    Returns publicly available plugins (Preset, Package, Shared).
    Does not include user's private uploaded plugins.
    """
    plugins = await get_marketplace_plugins(
        user_id=user.id,
        source_filter=source,
        search=search,
        sort=sort,
    )
    return PluginListResponse(plugins=plugins)


# =============================================================================
# Plugin Detail Endpoints
# =============================================================================


@router.get("/{plugin_name:path}", response_model=PluginInfo)
async def get_plugin_detail(
    plugin_name: str,
    user: UserInfo = Depends(get_current_user),
) -> PluginInfo:
    """Get plugin details.

    Args:
        plugin_name: Namespaced plugin name (e.g., "preset:research", "package:content-writer")
    """
    plugin = await get_plugin(user.id, plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")
    return plugin


@router.patch("/{plugin_name:path}", response_model=PluginInfo)
async def update_plugin_state_endpoint(
    plugin_name: str,
    request: PluginStateUpdateRequest,
    user: UserInfo = Depends(get_current_user),
) -> PluginInfo:
    """Update plugin enabled state for the current user."""
    plugin = await update_plugin_state(user.id, plugin_name, request.enabled)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")
    return plugin


# =============================================================================
# Plugin Rating Endpoints
# =============================================================================


@router.get("/{plugin_name:path}/rating", response_model=PluginRatingInfo)
async def get_plugin_rating(
    plugin_name: str,
    user: UserInfo = Depends(get_current_user),
) -> PluginRatingInfo:
    """Get rating summary for a plugin."""
    # Verify plugin exists
    plugin = await get_plugin(user.id, plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")

    return await plugin_db.get_plugin_rating_info(plugin_name)


@router.put("/{plugin_name:path}/rating", response_model=PluginRatingInfo)
async def rate_plugin(
    plugin_name: str,
    request: PluginRatingRequest,
    user: UserInfo = Depends(get_current_user),
) -> PluginRatingInfo:
    """Rate a plugin (1-5 stars).

    Only Package and Shared plugins can be rated.
    """
    # Verify plugin exists
    plugin = await get_plugin(user.id, plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")

    # Check if plugin can be rated
    if plugin.source not in (PluginSource.PACKAGE, PluginSource.SHARED):
        raise HTTPException(
            status_code=400,
            detail="Only Package and Shared plugins can be rated",
        )

    # Save rating
    await plugin_db.upsert_plugin_rating(user.id, plugin_name, request.rating)

    # Return updated rating info
    return await plugin_db.get_plugin_rating_info(plugin_name)


# =============================================================================
# Plugin Upload/Delete Endpoints
# =============================================================================


@router.post("/upload", response_model=PluginUploadResponse)
async def upload_plugin(
    file: UploadFile = File(..., description="Plugin ZIP file"),
    user: UserInfo = Depends(get_current_user),
) -> PluginUploadResponse:
    """Upload a plugin package.

    Accepts a ZIP file containing either:
    - An agent plugin (with AGENTS.md at root)
    - A skill plugin (with SKILL.md at root)

    The plugin will be extracted and registered for the current user.
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Only ZIP files are accepted",
        )

    # Validate the package
    validation = validate_plugin_package(file.file, file.filename)

    if not validation.valid:
        raise HTTPException(
            status_code=400,
            detail={"errors": validation.errors},
        )

    if not validation.plugin_name:
        raise HTTPException(
            status_code=400,
            detail="Could not determine plugin name from package",
        )

    # Create user-specific upload directory
    user_upload_dir = UPLOADED_PLUGINS_DIR / str(user.id)
    user_upload_dir.mkdir(parents=True, exist_ok=True)

    # Check if plugin already exists
    plugin_name = f"uploaded:{validation.plugin_name}"
    existing = await get_plugin(user.id, plugin_name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Plugin '{validation.plugin_name}' already exists. Delete it first to re-upload.",
        )

    try:
        # Extract the package
        plugin_dir = extract_plugin_package(
            file.file,
            user_upload_dir,
            validation.plugin_name,
        )

        # Register the plugin
        plugin_info = await register_uploaded_plugin(
            user_id=user.id,
            plugin_name=validation.plugin_name,
            plugin_dir=plugin_dir,
            plugin_type=validation.plugin_type or "agent",
            has_skills=validation.has_skills,
            skill_count=validation.skill_count,
        )

        logger.info(
            f"Plugin uploaded: {plugin_name} by user {user.id} "
            f"(type={validation.plugin_type}, skills={validation.skill_count})"
        )

        return PluginUploadResponse(
            success=True,
            plugin=plugin_info,
            warnings=validation.warnings,
        )

    except Exception as e:
        logger.exception(f"Failed to upload plugin: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process plugin: {e}",
        )


@router.delete("/{plugin_name:path}")
async def delete_plugin(
    plugin_name: str,
    user: UserInfo = Depends(get_current_user),
) -> dict:
    """Delete an uploaded plugin.

    Only uploaded plugins owned by the current user can be deleted.
    """
    # Parse plugin name
    if not plugin_name.startswith("uploaded:"):
        raise HTTPException(
            status_code=400,
            detail="Only uploaded plugins can be deleted",
        )

    # Check if plugin exists and belongs to user
    plugin = await get_plugin(user.id, plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")

    if plugin.source != PluginSource.UPLOADED:
        raise HTTPException(
            status_code=400,
            detail="Only uploaded plugins can be deleted",
        )

    # Delete the plugin
    success = await delete_uploaded_plugin(user.id, plugin_name)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete plugin",
        )

    logger.info(f"Plugin deleted: {plugin_name} by user {user.id}")

    return {"success": True, "message": f"Plugin '{plugin_name}' deleted"}


# =============================================================================
# Plugin Sharing Endpoints
# =============================================================================


@router.post("/{plugin_name:path}/share")
async def share_plugin(
    plugin_name: str,
    user: UserInfo = Depends(get_current_user),
) -> dict:
    """Share an uploaded plugin to the marketplace.

    Only uploaded plugins owned by the current user can be shared.
    Shared plugins become visible to all users in the marketplace.
    """
    # Verify it's an uploaded plugin
    if not plugin_name.startswith("uploaded:"):
        raise HTTPException(
            status_code=400,
            detail="Only uploaded plugins can be shared",
        )

    # Check if plugin exists and belongs to user
    plugin = await get_plugin(user.id, plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")

    if plugin.source != PluginSource.UPLOADED:
        raise HTTPException(
            status_code=400,
            detail="Only uploaded plugins can be shared",
        )

    # Extract actual name
    actual_name = plugin_name.split(":", 1)[1]

    # Update shared status
    updated = await plugin_db.update_uploaded_plugin_shared(user.id, actual_name, True)

    if not updated:
        raise HTTPException(
            status_code=500,
            detail="Failed to share plugin",
        )

    logger.info(f"Plugin shared: {plugin_name} by user {user.id}")

    return {"success": True, "message": f"Plugin '{plugin_name}' shared to marketplace"}


@router.delete("/{plugin_name:path}/share")
async def unshare_plugin(
    plugin_name: str,
    user: UserInfo = Depends(get_current_user),
) -> dict:
    """Remove a plugin from the marketplace (unshare).

    The plugin remains available to the owner but is no longer visible to others.
    Users who had enabled the shared plugin will retain access until they disable it.
    """
    # Verify it's an uploaded plugin
    if not plugin_name.startswith("uploaded:"):
        raise HTTPException(
            status_code=400,
            detail="Only uploaded plugins can be unshared",
        )

    # Check if plugin exists and belongs to user
    plugin = await get_plugin(user.id, plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")

    # Extract actual name
    actual_name = plugin_name.split(":", 1)[1]

    # Update shared and delisted status
    # Note: We set is_delisted=True to preserve access for existing users
    await plugin_db.update_uploaded_plugin_shared(user.id, actual_name, False)
    await plugin_db.update_uploaded_plugin_delisted(user.id, actual_name, True)

    logger.info(f"Plugin unshared: {plugin_name} by user {user.id}")

    return {"success": True, "message": f"Plugin '{plugin_name}' removed from marketplace"}
