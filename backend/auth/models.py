"""Pydantic models for authentication and user management."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """User role enum."""
    ADMIN = "admin"
    USER = "user"


class UserStatus(str, Enum):
    """User status enum."""
    ACTIVE = "active"
    DISABLED = "disabled"


class LoginRequest(BaseModel):
    """Request body for login endpoint."""
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Response body for login endpoint."""
    user: "UserInfo"
    message: str = "Login successful"


class UserInfo(BaseModel):
    """User information returned in API responses."""
    id: UUID
    username: str
    role: UserRole
    status: UserStatus
    created_at: datetime


class UserCreate(BaseModel):
    """Request body for creating a new user."""
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    password: str = Field(..., min_length=1)
    role: UserRole = UserRole.USER


class UserStatusUpdate(BaseModel):
    """Request body for updating user status."""
    status: UserStatus


# Update forward references
LoginResponse.model_rebuild()
