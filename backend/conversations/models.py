"""Pydantic models for conversation management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    """Request body for creating a new conversation."""
    title: str = Field(default="New Conversation", max_length=50)
    project_id: UUID | None = Field(default=None, description="可选：关联到项目")


class ConversationSummary(BaseModel):
    """Summary of a conversation for list display."""
    id: UUID
    title: str
    project_id: UUID | None = None
    updated_at: datetime


class Conversation(BaseModel):
    """Full conversation details."""
    id: UUID
    thread_id: str
    title: str
    project_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ConversationUpdate(BaseModel):
    """Request body for updating a conversation."""
    title: str = Field(..., min_length=1, max_length=50)
