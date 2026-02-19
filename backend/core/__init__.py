"""Core API routers for chat, files, and skills."""

from backend.core.chat import router as chat_router
from backend.core.files import router as files_router
from backend.core.skills import router as skills_router

__all__ = ["chat_router", "files_router", "skills_router"]
