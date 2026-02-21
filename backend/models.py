"""Pydantic models for API requests and responses."""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    thread_id: str
    message: str
    agent: str | None = None  # Explicit agent routing (skips supervisor)
    skill: str | None = None  # Explicit skill invocation (handled by AIME generic actor)
    file_ids: list[str] | None = None  # Uploaded file IDs to include in message
    project_file_ids: list[str] | None = None  # Project file IDs as context
    project_id: str | None = None  # Project ID for project file context


class ThreadCreate(BaseModel):
    """Response for thread creation."""

    thread_id: str
