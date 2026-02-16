"""API router for conversation management."""

import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status

from backend.aime.context_manager import ContextManager
from backend.auth.dependencies import get_current_user
from backend.auth.models import UserInfo
from backend.conversations.models import (
    Conversation,
    ConversationCreate,
    ConversationSummary,
    ConversationUpdate,
)
from backend.conversations import database as db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationListResponse:
    """Response model for conversation list."""
    def __init__(self, conversations: list[ConversationSummary], total: int):
        self.conversations = conversations
        self.total = total


@router.get("")
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    current_user: UserInfo = Depends(get_current_user)
) -> dict:
    """List conversations for the current user."""
    conversations, total = await db.list_user_conversations(
        user_id=current_user.id,
        limit=min(limit, 100),  # Max 100 per page
        offset=offset
    )
    return {
        "conversations": [c.model_dump() for c in conversations],
        "total": total
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    current_user: UserInfo = Depends(get_current_user)
) -> Conversation:
    """Create a new conversation."""
    thread_id = uuid.uuid4().hex[:8]
    conversation = await db.create_conversation(
        user_id=current_user.id,
        thread_id=thread_id,
        title=body.title
    )
    return conversation


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: UserInfo = Depends(get_current_user)
) -> Conversation:
    """Get a conversation by ID."""
    conversation = await db.get_conversation(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    return conversation


@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    current_user: UserInfo = Depends(get_current_user)
) -> Conversation:
    """Update a conversation's title."""
    conversation = await db.update_conversation_title(
        conversation_id=conversation_id,
        user_id=current_user.id,
        title=body.title
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: UserInfo = Depends(get_current_user)
) -> None:
    """Delete a conversation and clean up associated context cache."""
    # Get conversation first to get thread_id for cache cleanup
    conversation = await db.get_conversation(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    thread_id = conversation.thread_id

    # Delete conversation (CASCADE will clean up task_contexts in DB)
    deleted = await db.delete_conversation(conversation_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Clean up in-memory cache (T037)
    try:
        context_manager = ContextManager()
        await context_manager.cleanup_thread(thread_id)
    except Exception as e:
        logger.warning(f"Failed to cleanup context cache for thread {thread_id}: {e}")
