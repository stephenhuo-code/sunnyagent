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
    project_id: uuid.UUID | None = None,
    exclude_project: bool = False,
    current_user: UserInfo = Depends(get_current_user)
) -> dict:
    """List conversations for the current user.

    Args:
        limit: Maximum number of results
        offset: Offset for pagination
        project_id: Filter by specific project ID (optional)
        exclude_project: If True, only return conversations without a project (History)
    """
    conversations, total = await db.list_user_conversations(
        user_id=current_user.id,
        limit=min(limit, 100),  # Max 100 per page
        offset=offset,
        project_id=project_id,
        exclude_project=exclude_project,
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
    """Create a new conversation, optionally associating with a project."""
    # If project_id is provided, verify ownership
    if body.project_id:
        from backend.projects import database as projects_db
        if not await projects_db.check_project_ownership(body.project_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

    thread_id = uuid.uuid4().hex[:8]
    conversation = await db.create_conversation(
        user_id=current_user.id,
        thread_id=thread_id,
        title=body.title,
        project_id=body.project_id
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


# =============================================================================
# Project Association Endpoints
# =============================================================================


from pydantic import BaseModel, Field


class ConversationProjectAssociation(BaseModel):
    """Request body for associating a conversation with a project."""
    project_id: uuid.UUID = Field(..., description="目标项目 ID")


@router.post("/{conversation_id}/project")
async def add_conversation_to_project(
    conversation_id: uuid.UUID,
    body: ConversationProjectAssociation,
    current_user: UserInfo = Depends(get_current_user)
) -> dict:
    """Associate a conversation with a project."""
    # Check if conversation exists and belongs to user
    conversation = await db.get_conversation(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在"
        )

    # Check if already in this project
    if conversation.project_id == body.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="对话已属于该项目"
        )

    # Verify project ownership (import here to avoid circular imports)
    from backend.projects import database as projects_db
    if not await projects_db.check_project_ownership(body.project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    # Update conversation
    updated = await db.add_conversation_to_project(
        conversation_id, current_user.id, body.project_id
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在"
        )

    return {"message": "对话已添加到项目"}


@router.delete("/{conversation_id}/project", status_code=status.HTTP_204_NO_CONTENT)
async def remove_conversation_from_project(
    conversation_id: uuid.UUID,
    current_user: UserInfo = Depends(get_current_user)
) -> None:
    """Remove a conversation from its project (move to History)."""
    # Check if conversation exists
    conversation = await db.get_conversation(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在"
        )

    # Update conversation
    await db.remove_conversation_from_project(conversation_id, current_user.id)
