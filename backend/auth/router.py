"""FastAPI router for authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.auth.database import (
    get_user_by_username,
    create_user,
    list_users,
    delete_user,
    update_user_status,
    count_active_admins,
    user_exists,
)
from backend.auth.dependencies import get_current_user, require_admin
from backend.auth.models import (
    LoginRequest,
    LoginResponse,
    UserCreate,
    UserInfo,
    UserRole,
    UserStatusUpdate,
)
from backend.auth.security import verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response):
    """Authenticate user and return JWT token in cookie."""
    user_data = await get_user_by_username(request.username)

    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    if not verify_password(request.password, user_data["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    if user_data["status"] == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled. Please contact administrator."
        )

    # Create JWT token
    token = create_access_token({
        "sub": str(user_data["id"]),
        "username": user_data["username"],
        "role": user_data["role"]
    })

    # Set cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=86400,  # 24 hours
        samesite="lax",
        secure=False  # Set to True in production with HTTPS
    )

    user_info = UserInfo(
        id=user_data["id"],
        username=user_data["username"],
        role=UserRole(user_data["role"]),
        status=user_data["status"],
        created_at=user_data["created_at"]
    )

    return LoginResponse(user=user_info)


@router.post("/logout")
async def logout(response: Response):
    """Clear the authentication cookie."""
    response.delete_cookie(key="access_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: UserInfo = Depends(get_current_user)):
    """Get current user information."""
    return current_user


# User management endpoints (admin only)
users_router = APIRouter(prefix="/api/users", tags=["User Management"])


@users_router.get("", response_model=dict)
async def get_users(admin: UserInfo = Depends(require_admin)):
    """Get all users (admin only)."""
    users = await list_users()
    return {"users": users}


@users_router.post("", response_model=UserInfo, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_data: UserCreate,
    admin: UserInfo = Depends(require_admin)
):
    """Create a new user (admin only)."""
    # Check if username exists
    if await user_exists(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    return await create_user(
        username=user_data.username,
        password=user_data.password,
        role=user_data.role
    )


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_endpoint(
    user_id: str,
    admin: UserInfo = Depends(require_admin)
):
    """Delete a user (admin only)."""
    from uuid import UUID

    try:
        target_user_id = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID"
        )

    # Cannot delete self
    if target_user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    # Check if trying to delete last admin
    from backend.auth.database import get_user_by_id
    target_user = await get_user_by_id(target_user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if target_user["role"] == "admin" and target_user["status"] == "active":
        active_admins = await count_active_admins()
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last active administrator"
            )

    success = await delete_user(target_user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )


@users_router.patch("/{user_id}/status", response_model=UserInfo)
async def update_user_status_endpoint(
    user_id: str,
    status_update: UserStatusUpdate,
    admin: UserInfo = Depends(require_admin)
):
    """Update user status (admin only)."""
    from uuid import UUID

    try:
        target_user_id = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID"
        )

    # Cannot disable self
    if target_user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own status"
        )

    # Check if trying to disable last admin
    from backend.auth.database import get_user_by_id
    from backend.auth.models import UserStatus

    target_user = await get_user_by_id(target_user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if (target_user["role"] == "admin" and
        target_user["status"] == "active" and
        status_update.status == UserStatus.DISABLED):
        active_admins = await count_active_admins()
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot disable the last active administrator"
            )

    updated = await update_user_status(target_user_id, status_update.status)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return updated
