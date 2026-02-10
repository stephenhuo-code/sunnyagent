"""FastAPI dependencies for authentication and authorization."""

from uuid import UUID

from fastapi import Cookie, HTTPException, status

from backend.auth.database import get_user_by_id
from backend.auth.models import UserInfo, UserRole, UserStatus
from backend.auth.security import decode_access_token


async def get_current_user(access_token: str | None = Cookie(default=None)) -> UserInfo:
    """Get the current authenticated user from the JWT cookie."""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    payload = decode_access_token(access_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token"
        )

    user_data = await get_user_by_id(user_uuid)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if user_data["status"] == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled"
        )

    return UserInfo(
        id=user_data["id"],
        username=user_data["username"],
        role=UserRole(user_data["role"]),
        status=UserStatus(user_data["status"]),
        created_at=user_data["created_at"]
    )


async def require_admin(access_token: str | None = Cookie(default=None)) -> UserInfo:
    """Require the current user to be an admin."""
    user = await get_current_user(access_token)
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user
