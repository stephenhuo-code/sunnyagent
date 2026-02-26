"""Plugin management service layer.

Provides business logic for:
- Listing plugins from all sources (preset, package, uploaded, shared)
- Managing user plugin states (enable/disable)
- Merging registry data with database state
"""

import logging
from pathlib import Path
from uuid import UUID

from backend.plugins import database as plugin_db
from backend.plugins.models import (
    PluginInfo,
    PluginRatingInfo,
    PluginSource,
    PluginType,
    SkillType,
)
from backend.commands import get_commands_for_plugin
from backend.registry import AGENT_REGISTRY, AgentEntry
from backend.skills.registry import SKILL_REGISTRY, SkillEntry

logger = logging.getLogger(__name__)


# =============================================================================
# Plugin Listing
# =============================================================================


def _agent_entry_to_plugin_info(
    entry: AgentEntry,
    enabled: bool = True,
    rating: PluginRatingInfo | None = None,
) -> PluginInfo:
    """Convert an AgentEntry to PluginInfo."""
    # Determine source from entry.source
    source_map = {
        "preset": PluginSource.PRESET,
        "package": PluginSource.PACKAGE,
        "uploaded": PluginSource.UPLOADED,
        "shared": PluginSource.SHARED,
    }
    source = source_map.get(entry.source, PluginSource.PRESET)

    # Build namespaced name
    plugin_name = f"{source.value}:{entry.name}"

    # Query skills and commands for this agent (package agents only)
    skills_list: list[PluginInfo] | None = None
    commands_list: list[str] | None = None

    if source == PluginSource.PACKAGE:
        # Get skills
        agent_skill_source = f"package:{entry.name}"
        matching_skills = [
            skill for skill in SKILL_REGISTRY.values()
            if skill.source == agent_skill_source
        ]
        if matching_skills:
            skills_list = [
                _skill_entry_to_plugin_info(skill, enabled=enabled)
                for skill in matching_skills
            ]

        # Get commands
        matching_commands = get_commands_for_plugin(plugin_name)
        if matching_commands:
            commands_list = [cmd.name for cmd in matching_commands]

    return PluginInfo(
        name=plugin_name,
        display_name=entry.name.replace("-", " ").replace("_", " ").title(),
        type=PluginType.AGENT,
        source=source,
        description=entry.description,
        version="1.0.0",
        enabled=enabled,
        capabilities=entry.capabilities if entry.capabilities else None,
        commands=commands_list,
        rating=rating,
        skills=skills_list,
    )


def _skill_entry_to_plugin_info(
    entry: SkillEntry,
    enabled: bool = True,
    rating: PluginRatingInfo | None = None,
) -> PluginInfo:
    """Convert a SkillEntry to PluginInfo."""
    # Parse source from entry.source (e.g., "preset", "package:agent-name", "uploaded:user-id")
    source_str = entry.source
    if source_str.startswith("package:"):
        source = PluginSource.PACKAGE
    elif source_str.startswith("uploaded:"):
        source = PluginSource.UPLOADED
    elif source_str == "shared":
        source = PluginSource.SHARED
    elif source_str in ("preset", "custom"):
        source = PluginSource.PRESET
    else:
        source = PluginSource.PRESET

    # Build namespaced name
    plugin_name = f"{source.value}:{entry.name}"

    # All skills are atomic now (workflow skills removed)
    return PluginInfo(
        name=plugin_name,
        display_name=entry.name.replace("-", " ").replace("_", " ").title(),
        type=PluginType.SKILL,
        source=source,
        description=entry.description,
        version="1.0.0",
        enabled=enabled,
        skill_type=SkillType.ATOMIC,
        steps=None,
        rating=rating,
    )


async def get_all_plugins(
    user_id: UUID,
    source_filter: PluginSource | None = None,
    type_filter: PluginType | None = None,
    enabled_filter: bool | None = None,
    search: str | None = None,
) -> list[PluginInfo]:
    """Get all plugins visible to the user.

    Merges:
    - AGENT_REGISTRY (preset, package)
    - SKILL_REGISTRY (preset, custom, package)
    - Uploaded plugins (from database)
    - Shared plugins (from database)

    Applies user's enabled/disabled state from user_plugin_states.

    Note: Package plugins default to disabled and must be explicitly enabled.
    Preset/built-in plugins default to enabled.
    """
    plugins: list[PluginInfo] = []

    # Hot-load any newly added packages
    from backend.agents.loader import scan_and_load_new_packages

    newly_loaded = scan_and_load_new_packages()
    if newly_loaded:
        logger.info(f"Hot-loaded {len(newly_loaded)} new packages: {newly_loaded}")

    # Get user's plugin states from database
    disabled_plugins = await plugin_db.get_disabled_plugin_names(user_id)
    enabled_packages = await plugin_db.get_enabled_package_plugins(user_id)

    # 1. Add agents from AGENT_REGISTRY
    for entry in AGENT_REGISTRY.values():
        source = PluginSource.PACKAGE if entry.source == "package" else PluginSource.PRESET
        plugin_name = f"{source.value}:{entry.name}"

        # Package plugins default to disabled, others default to enabled
        if source == PluginSource.PACKAGE:
            enabled = plugin_name in enabled_packages
        else:
            enabled = plugin_name not in disabled_plugins

        # Apply filters
        if source_filter and source != source_filter:
            continue
        if type_filter and type_filter != PluginType.AGENT:
            continue
        if enabled_filter is not None and enabled != enabled_filter:
            continue

        plugin = _agent_entry_to_plugin_info(entry, enabled=enabled)

        # Apply search
        if search:
            search_lower = search.lower()
            if (
                search_lower not in plugin.name.lower()
                and search_lower not in plugin.display_name.lower()
                and search_lower not in plugin.description.lower()
            ):
                continue

        plugins.append(plugin)

    # 2. Add skills from SKILL_REGISTRY
    for entry in SKILL_REGISTRY.values():
        # Determine source
        if entry.source.startswith("package:"):
            source = PluginSource.PACKAGE
        elif entry.source.startswith("uploaded:"):
            source = PluginSource.UPLOADED
        elif entry.source == "shared":
            source = PluginSource.SHARED
        else:
            source = PluginSource.PRESET

        plugin_name = f"{source.value}:{entry.name}"

        # Package plugins default to disabled, others default to enabled
        if source == PluginSource.PACKAGE:
            enabled = plugin_name in enabled_packages
        else:
            enabled = plugin_name not in disabled_plugins

        # Apply filters
        if source_filter and source != source_filter:
            continue
        if type_filter and type_filter != PluginType.SKILL:
            continue
        if enabled_filter is not None and enabled != enabled_filter:
            continue

        plugin = _skill_entry_to_plugin_info(entry, enabled=enabled)

        # Apply search
        if search:
            search_lower = search.lower()
            if (
                search_lower not in plugin.name.lower()
                and search_lower not in plugin.display_name.lower()
                and search_lower not in plugin.description.lower()
            ):
                continue

        plugins.append(plugin)

    # 3. Add user's uploaded plugins from database
    if source_filter is None or source_filter == PluginSource.UPLOADED:
        uploaded = await plugin_db.get_user_uploaded_plugins(user_id)
        for up in uploaded:
            plugin_name = f"uploaded:{up.plugin_name}"
            enabled = plugin_name not in disabled_plugins

            if type_filter and type_filter.value != up.plugin_type:
                continue
            if enabled_filter is not None and enabled != enabled_filter:
                continue

            plugin = PluginInfo(
                name=plugin_name,
                display_name=up.display_name,
                type=PluginType(up.plugin_type),
                source=PluginSource.UPLOADED,
                description=up.description or "",
                version=up.version,
                author=up.author,
                enabled=enabled,
                uploader_id=up.user_id,
                is_delisted=up.is_delisted,
            )

            if search:
                search_lower = search.lower()
                if (
                    search_lower not in plugin.name.lower()
                    and search_lower not in plugin.display_name.lower()
                    and search_lower not in plugin.description.lower()
                ):
                    continue

            plugins.append(plugin)

    # Sort by name
    plugins.sort(key=lambda p: p.name)

    return plugins


async def get_plugin(user_id: UUID, plugin_name: str) -> PluginInfo | None:
    """Get a specific plugin by namespaced name.

    Args:
        user_id: Current user ID for state lookup
        plugin_name: Namespaced name (e.g., "preset:research", "package:content-writer")
    """
    # Parse plugin_name
    if ":" not in plugin_name:
        return None

    source_str, name = plugin_name.split(":", 1)

    try:
        source = PluginSource(source_str)
    except ValueError:
        return None

    # Determine enabled state based on source
    if source == PluginSource.PACKAGE:
        # Package plugins default to disabled
        enabled_packages = await plugin_db.get_enabled_package_plugins(user_id)
        enabled = plugin_name in enabled_packages
    else:
        # Other plugins default to enabled
        disabled_plugins = await plugin_db.get_disabled_plugin_names(user_id)
        enabled = plugin_name not in disabled_plugins

    # Look up in registries based on source and type
    # Check AGENT_REGISTRY first
    if name in AGENT_REGISTRY:
        entry = AGENT_REGISTRY[name]
        rating = None
        if source in (PluginSource.PACKAGE, PluginSource.SHARED):
            rating = await plugin_db.get_plugin_rating_info(plugin_name)
        return _agent_entry_to_plugin_info(entry, enabled=enabled, rating=rating)

    # Check SKILL_REGISTRY
    if name in SKILL_REGISTRY:
        entry = SKILL_REGISTRY[name]
        rating = None
        if source in (PluginSource.PACKAGE, PluginSource.SHARED):
            rating = await plugin_db.get_plugin_rating_info(plugin_name)
        return _skill_entry_to_plugin_info(entry, enabled=enabled, rating=rating)

    # Check uploaded plugins (if source is uploaded)
    if source == PluginSource.UPLOADED:
        uploaded = await plugin_db.get_uploaded_plugin(user_id, name)
        if uploaded:
            return PluginInfo(
                name=plugin_name,
                display_name=uploaded.display_name,
                type=PluginType(uploaded.plugin_type),
                source=PluginSource.UPLOADED,
                description=uploaded.description or "",
                version=uploaded.version,
                author=uploaded.author,
                enabled=enabled,
                uploader_id=uploaded.user_id,
                is_delisted=uploaded.is_delisted,
            )

    return None


async def get_marketplace_plugins(
    user_id: UUID,
    source_filter: PluginSource | None = None,
    search: str | None = None,
    sort: str = "name",
) -> list[PluginInfo]:
    """Get plugins available in the marketplace.

    Includes: Preset, Package, Shared (not Uploaded - those are user-private)
    """
    plugins: list[PluginInfo] = []
    disabled_plugins = await plugin_db.get_disabled_plugin_names(user_id)
    enabled_packages = await plugin_db.get_enabled_package_plugins(user_id)

    # 1. Add preset/package agents
    for entry in AGENT_REGISTRY.values():
        source = PluginSource.PACKAGE if entry.source == "package" else PluginSource.PRESET

        if source_filter and source != source_filter:
            continue

        plugin_name = f"{source.value}:{entry.name}"

        # Package plugins default to disabled, others default to enabled
        if source == PluginSource.PACKAGE:
            enabled = plugin_name in enabled_packages
        else:
            enabled = plugin_name not in disabled_plugins

        rating = None
        if source == PluginSource.PACKAGE:
            rating = await plugin_db.get_plugin_rating_info(plugin_name)

        plugin = _agent_entry_to_plugin_info(entry, enabled=enabled, rating=rating)

        if search:
            search_lower = search.lower()
            if (
                search_lower not in plugin.name.lower()
                and search_lower not in plugin.display_name.lower()
                and search_lower not in plugin.description.lower()
            ):
                continue

        plugins.append(plugin)

    # 2. Add preset/package skills
    for entry in SKILL_REGISTRY.values():
        if entry.source.startswith("package:"):
            source = PluginSource.PACKAGE
        elif entry.source in ("preset", "custom"):
            source = PluginSource.PRESET
        else:
            continue  # Skip uploaded/shared skills for now

        if source_filter and source != source_filter:
            continue

        plugin_name = f"{source.value}:{entry.name}"

        # Package plugins default to disabled, others default to enabled
        if source == PluginSource.PACKAGE:
            enabled = plugin_name in enabled_packages
        else:
            enabled = plugin_name not in disabled_plugins

        rating = None
        if source == PluginSource.PACKAGE:
            rating = await plugin_db.get_plugin_rating_info(plugin_name)

        plugin = _skill_entry_to_plugin_info(entry, enabled=enabled, rating=rating)

        if search:
            search_lower = search.lower()
            if (
                search_lower not in plugin.name.lower()
                and search_lower not in plugin.display_name.lower()
                and search_lower not in plugin.description.lower()
            ):
                continue

        plugins.append(plugin)

    # 3. Add shared plugins from database
    if source_filter is None or source_filter == PluginSource.SHARED:
        shared = await plugin_db.get_shared_plugins()
        for sp in shared:
            plugin_name = f"shared:{sp.plugin_name}"
            enabled = plugin_name not in disabled_plugins

            rating = await plugin_db.get_plugin_rating_info(plugin_name)

            plugin = PluginInfo(
                name=plugin_name,
                display_name=sp.display_name,
                type=PluginType(sp.plugin_type),
                source=PluginSource.SHARED,
                description=sp.description or "",
                version=sp.version,
                author=sp.author,
                enabled=enabled,
                uploader_id=sp.user_id,
                rating=rating,
            )

            if search:
                search_lower = search.lower()
                if (
                    search_lower not in plugin.name.lower()
                    and search_lower not in plugin.display_name.lower()
                    and search_lower not in plugin.description.lower()
                ):
                    continue

            plugins.append(plugin)

    # Sort
    if sort == "rating":
        plugins.sort(key=lambda p: (-(p.rating.average if p.rating else 0), p.name))
    elif sort == "recent":
        # For marketplace, we don't have created_at in PluginInfo, so just sort by name
        plugins.sort(key=lambda p: p.name)
    else:
        plugins.sort(key=lambda p: p.name)

    return plugins


# =============================================================================
# Plugin State Management
# =============================================================================


async def update_plugin_state(user_id: UUID, plugin_name: str, enabled: bool) -> PluginInfo | None:
    """Update a user's enabled state for a plugin.

    Returns updated PluginInfo or None if plugin not found.
    """
    # Update state in database
    await plugin_db.upsert_user_plugin_state(user_id, plugin_name, enabled)

    # Return updated plugin info
    return await get_plugin(user_id, plugin_name)


async def get_enabled_plugins_for_user(user_id: UUID) -> list[PluginInfo]:
    """Get all enabled plugins for a user.

    Used by AIME planner to filter available agents/skills.
    """
    return await get_all_plugins(user_id, enabled_filter=True)


async def is_plugin_enabled(user_id: UUID, plugin_name: str) -> bool:
    """Check if a plugin is enabled for a user.

    Package plugins default to disabled and must be explicitly enabled.
    Other plugins default to enabled unless explicitly disabled.
    """
    if plugin_name.startswith("package:"):
        # Package plugins must be explicitly enabled
        enabled_packages = await plugin_db.get_enabled_package_plugins(user_id)
        return plugin_name in enabled_packages
    else:
        # Other plugins default to enabled
        disabled = await plugin_db.get_disabled_plugin_names(user_id)
        return plugin_name not in disabled


# =============================================================================
# Plugin Upload/Delete
# =============================================================================


async def register_uploaded_plugin(
    user_id: UUID,
    plugin_name: str,
    plugin_dir: Path,
    plugin_type: str,
    has_skills: bool = False,
    skill_count: int = 0,
) -> PluginInfo:
    """Register an uploaded plugin in the database and runtime registries.

    Args:
        user_id: User who uploaded the plugin
        plugin_name: Name of the plugin
        plugin_dir: Path to extracted plugin directory
        plugin_type: "agent" or "skill"
        has_skills: Whether the agent has bundled skills
        skill_count: Number of skills in the package

    Returns:
        PluginInfo for the registered plugin
    """
    # Read AGENTS.md or SKILL.md for description
    description = ""
    if plugin_type == "agent":
        agents_md = plugin_dir / "AGENTS.md"
        if agents_md.exists():
            content = agents_md.read_text()
            # Extract first non-empty line as description
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    description = line[:200]
                    break
    else:
        skill_md = plugin_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text()
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    description = line[:200]
                    break

    # Create database record
    from backend.plugins.database import create_uploaded_plugin

    db_record = await create_uploaded_plugin(
        user_id=user_id,
        plugin_name=plugin_name,
        plugin_type=PluginType(plugin_type),
        display_name=plugin_name.replace("-", " ").replace("_", " ").title(),
        description=description,
        storage_path=str(plugin_dir),
    )

    # Register in runtime registry
    if plugin_type == "agent":
        from backend.plugins.loader import load_agent_from_directory

        load_agent_from_directory(plugin_dir, f"uploaded:{plugin_name}", user_id)

    elif plugin_type == "skill":
        from backend.skills.loader import load_skills_from_directory

        skills_count = load_skills_from_directory(plugin_dir, f"uploaded:{plugin_name}")
        logger.info(f"Registered {skills_count} skills from uploaded plugin: {plugin_name}")

    # Return plugin info
    return PluginInfo(
        name=f"uploaded:{plugin_name}",
        display_name=db_record.display_name,
        type=PluginType(plugin_type),
        source=PluginSource.UPLOADED,
        description=description,
        version="1.0.0",
        enabled=True,
        uploader_id=user_id,
    )


async def delete_uploaded_plugin(user_id: UUID, plugin_name: str) -> bool:
    """Delete an uploaded plugin.

    Removes from:
    - Database (uploaded_plugins, user_plugin_states, plugin_ratings)
    - Runtime registries (AGENT_REGISTRY, SKILL_REGISTRY)
    - File system (extracted plugin directory)

    Args:
        user_id: User ID who owns the plugin
        plugin_name: Namespaced plugin name (e.g., "uploaded:my-plugin")

    Returns:
        True if deleted successfully, False otherwise
    """
    import shutil
    from pathlib import Path

    # Extract the actual plugin name
    if not plugin_name.startswith("uploaded:"):
        return False

    actual_name = plugin_name.split(":", 1)[1]

    # Get storage path from database
    uploaded = await plugin_db.get_uploaded_plugin(user_id, actual_name)
    if not uploaded:
        return False

    # Delete from database
    await plugin_db.delete_uploaded_plugin(user_id, actual_name)

    # Remove from runtime registries
    if actual_name in AGENT_REGISTRY:
        del AGENT_REGISTRY[actual_name]
        logger.info(f"Removed agent from registry: {actual_name}")

    if actual_name in SKILL_REGISTRY:
        del SKILL_REGISTRY[actual_name]
        logger.info(f"Removed skill from registry: {actual_name}")

    # Delete files
    if uploaded.storage_path:
        storage_path = Path(uploaded.storage_path)
        if storage_path.exists():
            shutil.rmtree(storage_path)
            logger.info(f"Deleted plugin files: {storage_path}")

    return True
