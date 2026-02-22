"""Global settings for scheduled tasks.

Stores global enabled setting in the database using a simple key-value pattern.
"""

import logging
from typing import Optional

from backend.db import fetch, fetchrow, execute

logger = logging.getLogger(__name__)

# Settings keys
SETTING_GLOBAL_ENABLED = "scheduled_tasks.global_enabled"
SETTING_MAX_CONCURRENT_TASKS = "scheduled_tasks.max_concurrent_tasks"
SETTING_DEFAULT_TIMEOUT_MINUTES = "scheduled_tasks.default_timeout_minutes"


async def _ensure_settings_table() -> None:
    """Ensure the system_settings table exists."""
    await execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key VARCHAR(255) PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)


async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a system setting value.

    Args:
        key: Setting key
        default: Default value if key not found

    Returns:
        Setting value or default
    """
    try:
        row = await fetchrow(
            "SELECT value FROM system_settings WHERE key = $1",
            key,
        )
        if row:
            return row["value"]
        return default
    except Exception as e:
        logger.warning(f"Failed to get setting {key}: {e}")
        return default


async def set_setting(key: str, value: str) -> None:
    """Set a system setting value.

    Args:
        key: Setting key
        value: Setting value
    """
    try:
        await execute("""
            INSERT INTO system_settings (key, value, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (key) DO UPDATE
            SET value = $2, updated_at = NOW()
        """, key, value)
    except Exception as e:
        logger.error(f"Failed to set setting {key}: {e}")
        raise


async def get_global_enabled() -> bool:
    """Get whether scheduled tasks are globally enabled.

    Returns:
        True if enabled (default), False if disabled
    """
    value = await get_setting(SETTING_GLOBAL_ENABLED, "true")
    return value.lower() == "true"


async def set_global_enabled(enabled: bool) -> None:
    """Set whether scheduled tasks are globally enabled.

    Args:
        enabled: True to enable, False to disable
    """
    await set_setting(SETTING_GLOBAL_ENABLED, str(enabled).lower())
    logger.info(f"Scheduled tasks global enabled set to: {enabled}")


async def get_max_concurrent_tasks() -> int:
    """Get maximum concurrent tasks setting.

    Returns:
        Maximum concurrent tasks (default: 5)
    """
    value = await get_setting(SETTING_MAX_CONCURRENT_TASKS, "5")
    try:
        return int(value)
    except ValueError:
        return 5


async def set_max_concurrent_tasks(max_tasks: int) -> None:
    """Set maximum concurrent tasks.

    Args:
        max_tasks: Maximum concurrent tasks
    """
    await set_setting(SETTING_MAX_CONCURRENT_TASKS, str(max_tasks))


async def get_default_timeout_minutes() -> int:
    """Get default task timeout in minutes.

    Returns:
        Default timeout in minutes (default: 15)
    """
    value = await get_setting(SETTING_DEFAULT_TIMEOUT_MINUTES, "15")
    try:
        return int(value)
    except ValueError:
        return 15


async def set_default_timeout_minutes(timeout: int) -> None:
    """Set default task timeout in minutes.

    Args:
        timeout: Timeout in minutes
    """
    await set_setting(SETTING_DEFAULT_TIMEOUT_MINUTES, str(timeout))


async def get_all_settings() -> dict:
    """Get all scheduled tasks settings.

    Returns:
        Dict of all settings
    """
    return {
        "global_enabled": await get_global_enabled(),
        "max_concurrent_tasks": await get_max_concurrent_tasks(),
        "default_timeout_minutes": await get_default_timeout_minutes(),
    }


async def update_settings(
    global_enabled: Optional[bool] = None,
    max_concurrent_tasks: Optional[int] = None,
    default_timeout_minutes: Optional[int] = None,
) -> dict:
    """Update multiple settings at once.

    Args:
        global_enabled: Optional global enabled setting
        max_concurrent_tasks: Optional max concurrent tasks
        default_timeout_minutes: Optional default timeout

    Returns:
        Updated settings dict
    """
    if global_enabled is not None:
        await set_global_enabled(global_enabled)
    if max_concurrent_tasks is not None:
        await set_max_concurrent_tasks(max_concurrent_tasks)
    if default_timeout_minutes is not None:
        await set_default_timeout_minutes(default_timeout_minutes)

    return await get_all_settings()
