"""API router registry - unified entry point for all routers."""

from fastapi import FastAPI

from backend.auth.router import router as auth_router, users_router
from backend.conversations.router import router as conversations_router
from backend.projects.router import router as projects_router
from backend.core import chat_router, files_router, skills_router, system_router
from backend.scheduled_tasks.router import router as scheduled_tasks_router, admin_router as scheduled_tasks_admin_router


def register_routers(app: FastAPI) -> None:
    """Register all API routers to the FastAPI application.

    Router organization:
    - auth_router: /api/auth/* (login, logout, me)
    - users_router: /api/users/* (admin user management)
    - conversations_router: /api/conversations/*
    - projects_router: /api/projects/*
    - scheduled_tasks_router: /api/scheduled-tasks/*
    - scheduled_tasks_admin_router: /api/admin/scheduled-tasks/*
    - chat_router: /api/chat, /api/threads/*
    - files_router: /api/files/*
    - skills_router: /api/agents, /api/skills/*
    - system_router: /api/system/* (admin-only system settings)
    """
    # Domain routers (with prefix defined in router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(conversations_router)
    app.include_router(projects_router)
    app.include_router(scheduled_tasks_router)
    app.include_router(scheduled_tasks_admin_router)

    # Core routers (prefix defined here or in router)
    app.include_router(chat_router)
    app.include_router(files_router)
    app.include_router(skills_router)
    app.include_router(system_router)


__all__ = [
    "register_routers",
    "auth_router",
    "users_router",
    "conversations_router",
    "projects_router",
    "scheduled_tasks_router",
    "scheduled_tasks_admin_router",
    "chat_router",
    "files_router",
    "skills_router",
    "system_router",
]
