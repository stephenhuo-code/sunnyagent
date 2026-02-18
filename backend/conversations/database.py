"""Database operations for conversation management."""

from uuid import UUID

from backend.db import fetch, fetchrow, execute
from backend.conversations.models import Conversation, ConversationSummary


async def create_conversation(
    user_id: UUID, thread_id: str, title: str = "New Conversation", project_id: UUID | None = None
) -> Conversation:
    """Create a new conversation, optionally associating with a project."""
    if project_id:
        row = await fetchrow(
            """INSERT INTO conversations (user_id, thread_id, title, project_id)
               VALUES ($1, $2, $3, $4)
               RETURNING id, thread_id, title, project_id, created_at, updated_at""",
            user_id, thread_id, title[:50], project_id
        )
    else:
        row = await fetchrow(
            """INSERT INTO conversations (user_id, thread_id, title)
               VALUES ($1, $2, $3)
               RETURNING id, thread_id, title, project_id, created_at, updated_at""",
            user_id, thread_id, title[:50]
        )
    if row is None:
        raise RuntimeError("Failed to create conversation")
    return Conversation(
        id=row["id"],
        thread_id=row["thread_id"],
        title=row["title"],
        project_id=row["project_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


async def get_conversation(conversation_id: UUID, user_id: UUID) -> Conversation | None:
    """Get a conversation by ID (must belong to user)."""
    row = await fetchrow(
        """SELECT id, thread_id, title, project_id, created_at, updated_at
           FROM conversations
           WHERE id = $1 AND user_id = $2 AND NOT is_deleted""",
        conversation_id, user_id
    )
    if row:
        return Conversation(
            id=row["id"],
            thread_id=row["thread_id"],
            title=row["title"],
            project_id=row["project_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    return None


async def get_conversation_by_thread(thread_id: str, user_id: UUID) -> Conversation | None:
    """Get a conversation by thread ID (must belong to user)."""
    row = await fetchrow(
        """SELECT id, thread_id, title, project_id, created_at, updated_at
           FROM conversations
           WHERE thread_id = $1 AND user_id = $2 AND NOT is_deleted""",
        thread_id, user_id
    )
    if row:
        return Conversation(
            id=row["id"],
            thread_id=row["thread_id"],
            title=row["title"],
            project_id=row["project_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    return None


async def list_user_conversations(
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
    project_id: UUID | None = None,
    exclude_project: bool = False,
) -> tuple[list[ConversationSummary], int]:
    """List conversations for a user with pagination.

    Args:
        user_id: The user ID
        limit: Maximum number of results
        offset: Offset for pagination
        project_id: Filter by specific project ID (optional)
        exclude_project: If True, only return conversations without a project
    """
    # Build query conditions
    if project_id:
        # Filter by specific project
        count_row = await fetchrow(
            "SELECT COUNT(*) as total FROM conversations WHERE user_id = $1 AND project_id = $2 AND NOT is_deleted",
            user_id, project_id
        )
        rows = await fetch(
            """SELECT id, title, project_id, updated_at
               FROM conversations
               WHERE user_id = $1 AND project_id = $2 AND NOT is_deleted
               ORDER BY updated_at DESC
               LIMIT $3 OFFSET $4""",
            user_id, project_id, limit, offset
        )
    elif exclude_project:
        # Only conversations without a project (for History)
        count_row = await fetchrow(
            "SELECT COUNT(*) as total FROM conversations WHERE user_id = $1 AND project_id IS NULL AND NOT is_deleted",
            user_id
        )
        rows = await fetch(
            """SELECT id, title, project_id, updated_at
               FROM conversations
               WHERE user_id = $1 AND project_id IS NULL AND NOT is_deleted
               ORDER BY updated_at DESC
               LIMIT $2 OFFSET $3""",
            user_id, limit, offset
        )
    else:
        # All conversations
        count_row = await fetchrow(
            "SELECT COUNT(*) as total FROM conversations WHERE user_id = $1 AND NOT is_deleted",
            user_id
        )
        rows = await fetch(
            """SELECT id, title, project_id, updated_at
               FROM conversations
               WHERE user_id = $1 AND NOT is_deleted
               ORDER BY updated_at DESC
               LIMIT $2 OFFSET $3""",
            user_id, limit, offset
        )

    total = count_row["total"] if count_row else 0
    conversations = [
        ConversationSummary(
            id=row["id"],
            title=row["title"],
            project_id=row["project_id"],
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
           RETURNING id, thread_id, title, project_id, created_at, updated_at""",
        title[:50], conversation_id, user_id
    )
    if row:
        return Conversation(
            id=row["id"],
            thread_id=row["thread_id"],
            title=row["title"],
            project_id=row["project_id"],
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


async def add_conversation_to_project(
    conversation_id: UUID, user_id: UUID, project_id: UUID
) -> Conversation | None:
    """Associate a conversation with a project."""
    row = await fetchrow(
        """UPDATE conversations
           SET project_id = $1
           WHERE id = $2 AND user_id = $3 AND NOT is_deleted
           RETURNING id, thread_id, title, project_id, created_at, updated_at""",
        project_id, conversation_id, user_id
    )
    if row:
        return Conversation(
            id=row["id"],
            thread_id=row["thread_id"],
            title=row["title"],
            project_id=row["project_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    return None


async def remove_conversation_from_project(
    conversation_id: UUID, user_id: UUID
) -> Conversation | None:
    """Remove a conversation from its project."""
    row = await fetchrow(
        """UPDATE conversations
           SET project_id = NULL
           WHERE id = $1 AND user_id = $2 AND NOT is_deleted
           RETURNING id, thread_id, title, project_id, created_at, updated_at""",
        conversation_id, user_id
    )
    if row:
        return Conversation(
            id=row["id"],
            thread_id=row["thread_id"],
            title=row["title"],
            project_id=row["project_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    return None


async def get_conversation_project_id(conversation_id: UUID, user_id: UUID) -> UUID | None:
    """Get the project_id for a conversation."""
    row = await fetchrow(
        "SELECT project_id FROM conversations WHERE id = $1 AND user_id = $2 AND NOT is_deleted",
        conversation_id, user_id
    )
    return row["project_id"] if row else None
