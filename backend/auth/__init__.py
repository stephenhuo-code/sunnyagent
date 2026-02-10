"""Authentication and user management module."""

from backend.auth.models import (
    UserRole,
    UserStatus,
    LoginRequest,
    LoginResponse,
    UserInfo,
    UserCreate,
    UserStatusUpdate,
)
from backend.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from backend.auth.dependencies import get_current_user, require_admin

__all__ = [
    "UserRole",
    "UserStatus",
    "LoginRequest",
    "LoginResponse",
    "UserInfo",
    "UserCreate",
    "UserStatusUpdate",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "get_current_user",
    "require_admin",
]
