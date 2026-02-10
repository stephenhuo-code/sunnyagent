"""Reset admin password to ADMIN_PASSWORD from .env"""

import asyncio
import os
import sys
from pathlib import Path

# Load .env from project root
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from backend.db import init_pool, close_pool, execute
from backend.auth.database import get_user_by_username, create_user
from backend.auth.models import UserRole
from backend.auth.security import hash_password


async def reset_admin_password() -> bool:
    """Reset admin password to the value in ADMIN_PASSWORD environment variable.

    If the admin user doesn't exist, create it.
    """
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_password:
        print("Error: ADMIN_PASSWORD not set in .env")
        return False

    await init_pool()

    try:
        user = await get_user_by_username(admin_username)

        if not user:
            # User doesn't exist, create it
            print(f"User '{admin_username}' not found, creating...")
            await create_user(admin_username, admin_password, UserRole.ADMIN)
            print(f"✅ Admin user '{admin_username}' created")
            return True

        # User exists, reset password
        password_hash = hash_password(admin_password)
        await execute(
            "UPDATE users SET password_hash = $1 WHERE id = $2",
            password_hash, user["id"]
        )
        print(f"✅ Password reset for user '{admin_username}'")
        return True
    finally:
        await close_pool()


if __name__ == "__main__":
    success = asyncio.run(reset_admin_password())
    sys.exit(0 if success else 1)
