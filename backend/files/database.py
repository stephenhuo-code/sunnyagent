"""Database operations for file management."""

from uuid import UUID

from backend.db import fetch, fetchrow, execute
from backend.files.models import FileInfo, FileSummary


async def create_file(
    user_id: UUID,
    file_id: str,
    original_name: str,
    content_type: str | None,
    size_bytes: int,
    storage_path: str,
    conversation_id: UUID | None = None
) -> FileInfo:
    """Create a new file record."""
    row = await fetchrow(
        """INSERT INTO files (file_id, user_id, conversation_id, original_name, content_type, size_bytes, storage_path)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           RETURNING id, file_id, original_name, content_type, size_bytes, created_at""",
        file_id, user_id, conversation_id, original_name, content_type, size_bytes, storage_path
    )
    return FileInfo.from_db_row(row)


async def get_file(file_id: str, user_id: UUID) -> dict | None:
    """Get a file by file_id (must belong to user).

    Returns the raw database row including storage_path for internal use.
    """
    row = await fetchrow(
        """SELECT id, file_id, original_name, content_type, size_bytes, storage_path, created_at
           FROM files
           WHERE file_id = $1 AND user_id = $2 AND NOT is_deleted""",
        file_id, user_id
    )
    if row:
        return dict(row)
    return None


async def get_file_by_id(file_id: str) -> dict | None:
    """Get a file by file_id without user check (for internal use only).

    WARNING: This bypasses user permission check. Only use for system operations.
    """
    row = await fetchrow(
        """SELECT id, file_id, user_id, original_name, content_type, size_bytes, storage_path, created_at
           FROM files
           WHERE file_id = $1 AND NOT is_deleted""",
        file_id
    )
    if row:
        return dict(row)
    return None


async def list_user_files(user_id: UUID, limit: int = 50, offset: int = 0) -> tuple[list[FileSummary], int]:
    """List files for a user with pagination."""
    # Get total count
    count_row = await fetchrow(
        "SELECT COUNT(*) as total FROM files WHERE user_id = $1 AND NOT is_deleted",
        user_id
    )
    total = count_row["total"] if count_row else 0

    # Get files
    rows = await fetch(
        """SELECT file_id, original_name, size_bytes, created_at
           FROM files
           WHERE user_id = $1 AND NOT is_deleted
           ORDER BY created_at DESC
           LIMIT $2 OFFSET $3""",
        user_id, limit, offset
    )
    files = [
        FileSummary(
            file_id=row["file_id"],
            original_name=row["original_name"],
            size_bytes=row["size_bytes"],
            created_at=row["created_at"],
            download_url=f"/api/files/{row['file_id']}/{row['original_name']}"
        )
        for row in rows
    ]
    return files, total


async def delete_file(file_id: str, user_id: UUID) -> bool:
    """Soft delete a file."""
    result = await execute(
        """UPDATE files
           SET is_deleted = TRUE
           WHERE file_id = $1 AND user_id = $2 AND NOT is_deleted""",
        file_id, user_id
    )
    return "UPDATE 1" in result


async def get_file_storage_path(file_id: str, user_id: UUID) -> str | None:
    """Get the storage path for a file (must belong to user)."""
    row = await fetchrow(
        """SELECT storage_path
           FROM files
           WHERE file_id = $1 AND user_id = $2 AND NOT is_deleted""",
        file_id, user_id
    )
    if row:
        return row["storage_path"]
    return None
