"""Database CRUD operations for plugin management tables."""

import logging
from datetime import datetime
from uuid import UUID

from backend.db import get_pool
from backend.plugins.models import (
    PluginRating,
    PluginRatingInfo,
    PluginType,
    UploadedPlugin,
    UserPluginState,
)

logger = logging.getLogger(__name__)


# =============================================================================
# User Plugin States CRUD
# =============================================================================


async def get_user_plugin_state(user_id: UUID, plugin_name: str) -> UserPluginState | None:
    """Get a user's state for a specific plugin."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, user_id, plugin_name, enabled, created_at, updated_at
        FROM user_plugin_states
        WHERE user_id = $1 AND plugin_name = $2
        """,
        user_id,
        plugin_name,
    )
    if row:
        return UserPluginState(**dict(row))
    return None


async def get_user_plugin_states(user_id: UUID) -> list[UserPluginState]:
    """Get all plugin states for a user."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT id, user_id, plugin_name, enabled, created_at, updated_at
        FROM user_plugin_states
        WHERE user_id = $1
        ORDER BY plugin_name
        """,
        user_id,
    )
    return [UserPluginState(**dict(row)) for row in rows]


async def get_enabled_plugin_names(user_id: UUID) -> set[str]:
    """Get names of all explicitly enabled plugins for a user."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT plugin_name
        FROM user_plugin_states
        WHERE user_id = $1 AND enabled = TRUE
        """,
        user_id,
    )
    return {row["plugin_name"] for row in rows}


async def get_disabled_plugin_names(user_id: UUID) -> set[str]:
    """Get names of all explicitly disabled plugins for a user."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT plugin_name
        FROM user_plugin_states
        WHERE user_id = $1 AND enabled = FALSE
        """,
        user_id,
    )
    return {row["plugin_name"] for row in rows}


async def get_enabled_package_plugins(user_id: UUID) -> set[str]:
    """Get names of explicitly enabled package plugins for a user.

    Package plugins default to disabled; only return those explicitly enabled.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT plugin_name
        FROM user_plugin_states
        WHERE user_id = $1 AND plugin_name LIKE 'package:%' AND enabled = TRUE
        """,
        user_id,
    )
    return {row["plugin_name"] for row in rows}


async def upsert_user_plugin_state(
    user_id: UUID, plugin_name: str, enabled: bool
) -> UserPluginState:
    """Create or update a user's plugin state."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO user_plugin_states (user_id, plugin_name, enabled)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, plugin_name)
        DO UPDATE SET enabled = $3, updated_at = NOW()
        RETURNING id, user_id, plugin_name, enabled, created_at, updated_at
        """,
        user_id,
        plugin_name,
        enabled,
    )
    return UserPluginState(**dict(row))


# =============================================================================
# Uploaded Plugins CRUD
# =============================================================================


async def create_uploaded_plugin(
    user_id: UUID,
    plugin_name: str,
    plugin_type: PluginType,
    display_name: str,
    storage_path: str,
    description: str | None = None,
    version: str = "1.0.0",
    author: str | None = None,
) -> UploadedPlugin:
    """Create an uploaded plugin record."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO uploaded_plugins
            (user_id, plugin_name, plugin_type, display_name, description, version, author, storage_path)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id, user_id, plugin_name, plugin_type, display_name, description,
                  version, author, storage_path, is_shared, is_delisted, created_at, updated_at
        """,
        user_id,
        plugin_name,
        plugin_type.value,
        display_name,
        description,
        version,
        author,
        storage_path,
    )
    return UploadedPlugin(**dict(row))


async def get_uploaded_plugin(user_id: UUID, plugin_name: str) -> UploadedPlugin | None:
    """Get an uploaded plugin by user and name."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, user_id, plugin_name, plugin_type, display_name, description,
               version, author, storage_path, is_shared, is_delisted, created_at, updated_at
        FROM uploaded_plugins
        WHERE user_id = $1 AND plugin_name = $2
        """,
        user_id,
        plugin_name,
    )
    if row:
        return UploadedPlugin(**dict(row))
    return None


async def get_uploaded_plugin_by_id(plugin_id: UUID) -> UploadedPlugin | None:
    """Get an uploaded plugin by ID."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, user_id, plugin_name, plugin_type, display_name, description,
               version, author, storage_path, is_shared, is_delisted, created_at, updated_at
        FROM uploaded_plugins
        WHERE id = $1
        """,
        plugin_id,
    )
    if row:
        return UploadedPlugin(**dict(row))
    return None


async def get_user_uploaded_plugins(user_id: UUID) -> list[UploadedPlugin]:
    """Get all uploaded plugins for a user."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT id, user_id, plugin_name, plugin_type, display_name, description,
               version, author, storage_path, is_shared, is_delisted, created_at, updated_at
        FROM uploaded_plugins
        WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        user_id,
    )
    return [UploadedPlugin(**dict(row)) for row in rows]


async def get_shared_plugins() -> list[UploadedPlugin]:
    """Get all shared plugins (not delisted)."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT id, user_id, plugin_name, plugin_type, display_name, description,
               version, author, storage_path, is_shared, is_delisted, created_at, updated_at
        FROM uploaded_plugins
        WHERE is_shared = TRUE AND is_delisted = FALSE
        ORDER BY created_at DESC
        """
    )
    return [UploadedPlugin(**dict(row)) for row in rows]


async def update_uploaded_plugin_shared(
    user_id: UUID, plugin_name: str, is_shared: bool
) -> UploadedPlugin | None:
    """Update shared status of an uploaded plugin."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE uploaded_plugins
        SET is_shared = $3, updated_at = NOW()
        WHERE user_id = $1 AND plugin_name = $2
        RETURNING id, user_id, plugin_name, plugin_type, display_name, description,
                  version, author, storage_path, is_shared, is_delisted, created_at, updated_at
        """,
        user_id,
        plugin_name,
        is_shared,
    )
    if row:
        return UploadedPlugin(**dict(row))
    return None


async def update_uploaded_plugin_delisted(
    user_id: UUID, plugin_name: str, is_delisted: bool
) -> UploadedPlugin | None:
    """Update delisted status of an uploaded plugin."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE uploaded_plugins
        SET is_delisted = $3, updated_at = NOW()
        WHERE user_id = $1 AND plugin_name = $2
        RETURNING id, user_id, plugin_name, plugin_type, display_name, description,
                  version, author, storage_path, is_shared, is_delisted, created_at, updated_at
        """,
        user_id,
        plugin_name,
        is_delisted,
    )
    if row:
        return UploadedPlugin(**dict(row))
    return None


async def delete_uploaded_plugin(user_id: UUID, plugin_name: str) -> bool:
    """Delete an uploaded plugin. Returns True if deleted."""
    pool = await get_pool()
    result = await pool.execute(
        """
        DELETE FROM uploaded_plugins
        WHERE user_id = $1 AND plugin_name = $2 AND is_shared = FALSE
        """,
        user_id,
        plugin_name,
    )
    # Result format: "DELETE N"
    return result.endswith("1")


# =============================================================================
# Plugin Ratings CRUD
# =============================================================================


async def get_user_plugin_rating(user_id: UUID, plugin_name: str) -> PluginRating | None:
    """Get a user's rating for a plugin."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, user_id, plugin_name, rating, created_at, updated_at
        FROM plugin_ratings
        WHERE user_id = $1 AND plugin_name = $2
        """,
        user_id,
        plugin_name,
    )
    if row:
        return PluginRating(**dict(row))
    return None


async def upsert_plugin_rating(user_id: UUID, plugin_name: str, rating: int) -> PluginRating:
    """Create or update a user's rating for a plugin."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO plugin_ratings (user_id, plugin_name, rating)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, plugin_name)
        DO UPDATE SET rating = $3, updated_at = NOW()
        RETURNING id, user_id, plugin_name, rating, created_at, updated_at
        """,
        user_id,
        plugin_name,
        rating,
    )
    return PluginRating(**dict(row))


async def get_plugin_rating_info(plugin_name: str) -> PluginRatingInfo:
    """Get aggregated rating info for a plugin."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT
            COALESCE(AVG(rating)::float, 0) as average,
            COUNT(*)::int as count
        FROM plugin_ratings
        WHERE plugin_name = $1
        """,
        plugin_name,
    )
    return PluginRatingInfo(average=row["average"], count=row["count"])


async def delete_plugin_ratings(plugin_name: str) -> int:
    """Delete all ratings for a plugin. Returns count deleted."""
    pool = await get_pool()
    result = await pool.execute(
        """
        DELETE FROM plugin_ratings
        WHERE plugin_name = $1
        """,
        plugin_name,
    )
    # Result format: "DELETE N"
    return int(result.split()[-1])
