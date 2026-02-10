"""Database operations for conversation management."""

from uuid import UUID

from backend.db import fetch, fetchrow, execute
from backend.conversations.models import Conversation, ConversationSummary


async def create_conversation(user_id: UUID, thread_id: str, title: str = "New Conversation") -> Conversation:
    """Create a new conversation."""
    row = await fetchrow(
        """INSERT INTO conversations (user_id, thread_id, title)
           VALUES ($1, $2, $3)
           RETURNING id, thread_id, title, created_at, updated_at""",
        user_id, thread_id, title[:50]  # Truncate to 50 chars
    )
    return Conversation(
        id=row["id"],
        thread_id=row["thread_id"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


async def get_conversation(conversation_id: UUID, user_id: UUID) -> Conversation | None:
    """Get a conversation by ID (must belong to user)."""
    row = await fetchrow(
        """SELECT id, thread_id, title, created_at, updated_at
           FROM conversations
           WHERE id = $1 AND user_id = $2 AND NOT is_deleted""",
        conversation_id, user_id
    )
    if row:
        return Conversation(
            id=row["id"],
            thread_id=row["thread_id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    return None


async def get_conversation_by_thread(thread_id: str, user_id: UUID) -> Conversation | None:
    """Get a conversation by thread ID (must belong to user)."""
    row = await fetchrow(
        """SELECT id, thread_id, title, created_at, updated_at
           FROM conversations
           WHERE thread_id = $1 AND user_id = $2 AND NOT is_deleted""",
        thread_id, user_id
    )
    if row:
        return Conversation(
            id=row["id"],
            thread_id=row["thread_id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    return None


async def list_user_conversations(user_id: UUID, limit: int = 50, offset: int = 0) -> tuple[list[ConversationSummary], int]:
    """List conversations for a user with pagination."""
    # Get total count
    count_row = await fetchrow(
        "SELECT COUNT(*) as total FROM conversations WHERE user_id = $1 AND NOT is_deleted",
        user_id
    )
    total = count_row["total"] if count_row else 0

    # Get conversations
    rows = await fetch(
        """SELECT id, title, updated_at
           FROM conversations
           WHERE user_id = $1 AND NOT is_deleted
           ORDER BY updated_at DESC
           LIMIT $2 OFFSET $3""",
        user_id, limit, offset
    )
    conversations = [
        ConversationSummary(
            id=row["id"],
            title=row["title"],
            updated_at=row["updated_at"]
        )
        for row in rows
    ]
    return conversations, total


async def update_conversation_title(conversation_id: UUID, user_id: UUID, title: str) -> Conversation | None:
    """Update a conversation's title."""
    row = await fetchrow(
        """UPDATE conversations
           SET title = $1
           WHERE id = $2 AND user_id = $3 AND NOT is_deleted
           RETURNING id, thread_id, title, created_at, updated_at""",
        title[:50], conversation_id, user_id
    )
    if row:
        return Conversation(
            id=row["id"],
            thread_id=row["thread_id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    return None


async def delete_conversation(conversation_id: UUID, user_id: UUID) -> bool:
    """Soft delete a conversation."""
    result = await execute(
        """UPDATE conversations
           SET is_deleted = TRUE
           WHERE id = $1 AND user_id = $2 AND NOT is_deleted""",
        conversation_id, user_id
    )
    return "UPDATE 1" in result


async def touch_conversation(thread_id: str, user_id: UUID) -> None:
    """Update the updated_at timestamp for a conversation."""
    await execute(
        """UPDATE conversations
           SET updated_at = NOW()
           WHERE thread_id = $1 AND user_id = $2 AND NOT is_deleted""",
        thread_id, user_id
    )
