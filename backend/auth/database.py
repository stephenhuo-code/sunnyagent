"""Database operations for user management."""

import logging
from datetime import datetime
from uuid import UUID

from backend.db import fetch, fetchrow, fetchval, execute
from backend.auth.models import UserInfo, UserRole, UserStatus
from backend.auth.security import hash_password

logger = logging.getLogger(__name__)


async def get_user_by_username(username: str) -> dict | None:
    """Get a user by username (case-insensitive)."""
    row = await fetchrow(
        "SELECT id, username, password_hash, role, status, created_at FROM users WHERE LOWER(username) = LOWER($1)",
        username
    )
    if row:
        return dict(row)
    return None


async def get_user_by_id(user_id: UUID) -> dict | None:
    """Get a user by ID."""
    row = await fetchrow(
        "SELECT id, username, password_hash, role, status, created_at FROM users WHERE id = $1",
        user_id
    )
    if row:
        return dict(row)
    return None


async def create_user(username: str, password: str, role: UserRole = UserRole.USER) -> UserInfo:
    """Create a new user."""
    password_hash = hash_password(password)
    row = await fetchrow(
        """INSERT INTO users (username, password_hash, role)
           VALUES ($1, $2, $3)
           RETURNING id, username, role, status, created_at""",
        username, password_hash, role.value
    )
    user_info = UserInfo(
        id=row["id"],
        username=row["username"],
        role=UserRole(row["role"]),
        status=UserStatus(row["status"]),
        created_at=row["created_at"]
    )

    # Sync user to Langfuse (fire and forget, don't block on failure)
    await _sync_user_to_langfuse(str(user_info.id), username)

    return user_info


async def update_user_status(user_id: UUID, status: UserStatus) -> UserInfo | None:
    """Update a user's status."""
    row = await fetchrow(
        """UPDATE users SET status = $1 WHERE id = $2
           RETURNING id, username, role, status, created_at""",
        status.value, user_id
    )
    if row:
        user_info = UserInfo(
            id=row["id"],
            username=row["username"],
            role=UserRole(row["role"]),
            status=UserStatus(row["status"]),
            created_at=row["created_at"]
        )

        # Sync status to Langfuse
        if status == UserStatus.DISABLED:
            await _disable_user_in_langfuse(str(user_id))

        return user_info
    return None


async def delete_user(user_id: UUID) -> bool:
    """Delete a user by ID."""
    # First delete user from Langfuse
    await _delete_user_from_langfuse(str(user_id))

    result = await execute("DELETE FROM users WHERE id = $1", user_id)
    return result == "DELETE 1"


async def list_users() -> list[UserInfo]:
    """List all users."""
    rows = await fetch(
        "SELECT id, username, role, status, created_at FROM users ORDER BY created_at DESC"
    )
    return [
        UserInfo(
            id=row["id"],
            username=row["username"],
            role=UserRole(row["role"]),
            status=UserStatus(row["status"]),
            created_at=row["created_at"]
        )
        for row in rows
    ]


async def count_active_admins() -> int:
    """Count the number of active admin users."""
    count = await fetchval(
        "SELECT COUNT(*) FROM users WHERE role = 'admin' AND status = 'active'"
    )
    return count or 0


async def user_exists(username: str) -> bool:
    """Check if a user with the given username exists."""
    count = await fetchval(
        "SELECT COUNT(*) FROM users WHERE LOWER(username) = LOWER($1)",
        username
    )
    return count > 0


async def get_user_count() -> int:
    """Get total user count."""
    count = await fetchval("SELECT COUNT(*) FROM users")
    return count or 0


async def init_default_admin() -> bool:
    """Create default admin user if no users exist.

    Reads ADMIN_USERNAME and ADMIN_PASSWORD from environment variables.
    Returns True if admin was created, False otherwise.
    """
    import os

    # Check if any users exist
    user_count = await get_user_count()
    if user_count > 0:
        return False

    # Get credentials from environment
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_password:
        # Generate a random password if not set
        import secrets
        admin_password = secrets.token_urlsafe(16)
        print(f"\n{'='*60}")
        print("FIRST RUN: Default admin user created")
        print(f"  Username: {admin_username}")
        print(f"  Password: {admin_password}")
        print("IMPORTANT: Save this password - it will not be shown again!")
        print(f"{'='*60}\n")

    await create_user(admin_username, admin_password, UserRole.ADMIN)
    return True


# ============== Langfuse User Sync Helpers ==============


async def _sync_user_to_langfuse(user_id: str, username: str) -> None:
    """Sync user to Langfuse (create if not exists).

    This is fire-and-forget - failures are logged but don't block user creation.
    """
    try:
        from backend.services.langfuse_admin_client import get_langfuse_admin_client

        client = get_langfuse_admin_client()
        if not client.enabled:
            return

        # Create user in Langfuse (using username as email for now)
        # In a real system, you'd have a proper email field
        email = f"{username}@sunnyagent.local"
        langfuse_user = await client.create_user(email, username)

        if langfuse_user:
            # Store mapping in database
            await _store_langfuse_mapping(user_id, langfuse_user.id, email)
            logger.info(f"Synced user {username} to Langfuse")

    except Exception as e:
        logger.warning(f"Failed to sync user {username} to Langfuse: {e}")


async def _disable_user_in_langfuse(user_id: str) -> None:
    """Disable user in Langfuse.

    This is fire-and-forget - failures are logged but don't block status update.
    """
    try:
        from backend.services.langfuse_admin_client import get_langfuse_admin_client

        client = get_langfuse_admin_client()
        if not client.enabled:
            return

        # Get Langfuse user ID from mapping
        langfuse_user_id = await _get_langfuse_user_id(user_id)
        if langfuse_user_id:
            await client.disable_user(langfuse_user_id)
            await _update_langfuse_mapping_status(user_id, "disabled")
            logger.info(f"Disabled user {user_id} in Langfuse")

    except Exception as e:
        logger.warning(f"Failed to disable user {user_id} in Langfuse: {e}")


async def _delete_user_from_langfuse(user_id: str) -> None:
    """Delete user from Langfuse.

    This is fire-and-forget - failures are logged but don't block user deletion.
    """
    try:
        from backend.services.langfuse_admin_client import get_langfuse_admin_client

        client = get_langfuse_admin_client()
        if not client.enabled:
            return

        # Get Langfuse user ID from mapping
        langfuse_user_id = await _get_langfuse_user_id(user_id)
        if langfuse_user_id:
            await client.delete_user(langfuse_user_id)
            await _delete_langfuse_mapping(user_id)
            logger.info(f"Deleted user {user_id} from Langfuse")

    except Exception as e:
        logger.warning(f"Failed to delete user {user_id} from Langfuse: {e}")


async def _store_langfuse_mapping(
    sunnyagent_user_id: str, langfuse_user_id: str, email: str
) -> None:
    """Store mapping between SunnyAgent and Langfuse user IDs."""
    try:
        await execute(
            """INSERT INTO langfuse_user_mapping
               (sunnyagent_user_id, langfuse_user_id, langfuse_email, status)
               VALUES ($1, $2, $3, 'active')
               ON CONFLICT (sunnyagent_user_id) DO UPDATE
               SET langfuse_user_id = $2, langfuse_email = $3, status = 'active', updated_at = NOW()""",
            sunnyagent_user_id, langfuse_user_id, email
        )
    except Exception as e:
        logger.warning(f"Failed to store Langfuse mapping: {e}")


async def _get_langfuse_user_id(sunnyagent_user_id: str) -> str | None:
    """Get Langfuse user ID from mapping."""
    try:
        result = await fetchval(
            "SELECT langfuse_user_id FROM langfuse_user_mapping WHERE sunnyagent_user_id = $1",
            sunnyagent_user_id
        )
        return result
    except Exception as e:
        logger.warning(f"Failed to get Langfuse mapping: {e}")
        return None


async def _update_langfuse_mapping_status(sunnyagent_user_id: str, status: str) -> None:
    """Update Langfuse mapping status."""
    try:
        await execute(
            "UPDATE langfuse_user_mapping SET status = $1, updated_at = NOW() WHERE sunnyagent_user_id = $2",
            status, sunnyagent_user_id
        )
    except Exception as e:
        logger.warning(f"Failed to update Langfuse mapping status: {e}")


async def _delete_langfuse_mapping(sunnyagent_user_id: str) -> None:
    """Delete Langfuse mapping."""
    try:
        await execute(
            "DELETE FROM langfuse_user_mapping WHERE sunnyagent_user_id = $1",
            sunnyagent_user_id
        )
    except Exception as e:
        logger.warning(f"Failed to delete Langfuse mapping: {e}")


async def get_users_by_ids(user_ids: list[str]) -> dict[str, str]:
    """
    Batch query usernames by user IDs.

    Args:
        user_ids: List of user UUID strings

    Returns:
        Dict[user_id, username], users not found are not included in the result
    """
    if not user_ids:
        return {}

    # Filter valid UUIDs
    valid_uuids: list[UUID] = []
    for uid in user_ids:
        try:
            valid_uuids.append(UUID(uid))
        except (ValueError, TypeError):
            continue

    if not valid_uuids:
        return {}

    rows = await fetch(
        "SELECT id, username FROM users WHERE id = ANY($1::uuid[])",
        valid_uuids
    )
    return {str(row["id"]): row["username"] for row in rows}
