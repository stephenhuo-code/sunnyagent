"""Pydantic models for conversation management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    """Request body for creating a new conversation."""
    title: str = Field(default="New Conversation", max_length=50)


class ConversationSummary(BaseModel):
    """Summary of a conversation for list display."""
    id: UUID
    title: str
    updated_at: datetime


class Conversation(BaseModel):
    """Full conversation details."""
    id: UUID
    thread_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationUpdate(BaseModel):
    """Request body for updating a conversation."""
    title: str = Field(..., min_length=1, max_length=50)
