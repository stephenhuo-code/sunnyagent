"""Database operations for user management."""

from datetime import datetime
from uuid import UUID

from backend.db import fetch, fetchrow, fetchval, execute
from backend.auth.models import UserInfo, UserRole, UserStatus
from backend.auth.security import hash_password


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
    return UserInfo(
        id=row["id"],
        username=row["username"],
        role=UserRole(row["role"]),
        status=UserStatus(row["status"]),
        created_at=row["created_at"]
    )


async def update_user_status(user_id: UUID, status: UserStatus) -> UserInfo | None:
    """Update a user's status."""
    row = await fetchrow(
        """UPDATE users SET status = $1 WHERE id = $2
           RETURNING id, username, role, status, created_at""",
        status.value, user_id
    )
    if row:
        return UserInfo(
            id=row["id"],
            username=row["username"],
            role=UserRole(row["role"]),
            status=UserStatus(row["status"]),
            created_at=row["created_at"]
        )
    return None


async def delete_user(user_id: UUID) -> bool:
    """Delete a user by ID."""
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
