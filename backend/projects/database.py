"""Database operations for project management."""

import os
import shutil
from uuid import UUID

from backend.db import fetch, fetchrow, execute
from backend.projects.models import (
    ProjectDetail,
    ProjectSummary,
    ProjectFileSummary,
    ProjectConversationSummary,
)


# =============================================================================
# Project CRUD Operations
# =============================================================================


async def create_project(user_id: UUID, name: str, username: str) -> ProjectDetail:
    """Create a new project."""
    row = await fetchrow(
        """INSERT INTO projects (user_id, name)
           VALUES ($1, $2)
           RETURNING id, name, created_at, updated_at""",
        user_id, name.strip()
    )
    assert row is not None, "INSERT should always return a row"
    return ProjectDetail(
        id=row["id"],
        name=row["name"],
        creator_name=username,
        file_count=0,
        conversation_count=0,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def get_project(project_id: UUID, user_id: UUID) -> ProjectDetail | None:
    """Get a project by ID (must belong to user)."""
    row = await fetchrow(
        """SELECT p.id, p.name, p.created_at, p.updated_at,
                  u.username as creator_name,
                  (SELECT COUNT(*) FROM project_files WHERE project_id = p.id) as file_count,
                  (SELECT COUNT(*) FROM conversations WHERE project_id = p.id AND NOT is_deleted) as conversation_count
           FROM projects p
           JOIN users u ON u.id = p.user_id
           WHERE p.id = $1 AND p.user_id = $2 AND NOT p.is_deleted""",
        project_id, user_id
    )
    if row:
        return ProjectDetail(
            id=row["id"],
            name=row["name"],
            creator_name=row["creator_name"],
            file_count=row["file_count"],
            conversation_count=row["conversation_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    return None


async def list_user_projects(user_id: UUID) -> list[ProjectSummary]:
    """List all projects for a user."""
    rows = await fetch(
        """SELECT p.id, p.name, p.created_at, p.updated_at,
                  u.username as creator_name,
                  (SELECT COUNT(*) FROM project_files WHERE project_id = p.id) as file_count,
                  (SELECT COUNT(*) FROM conversations WHERE project_id = p.id AND NOT is_deleted) as conversation_count
           FROM projects p
           JOIN users u ON u.id = p.user_id
           WHERE p.user_id = $1 AND NOT p.is_deleted
           ORDER BY p.updated_at DESC""",
        user_id
    )
    return [
        ProjectSummary(
            id=row["id"],
            name=row["name"],
            creator_name=row["creator_name"],
            file_count=row["file_count"],
            conversation_count=row["conversation_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


async def update_project(project_id: UUID, user_id: UUID, name: str, username: str) -> ProjectDetail | None:
    """Update a project's name."""
    row = await fetchrow(
        """UPDATE projects
           SET name = $1
           WHERE id = $2 AND user_id = $3 AND NOT is_deleted
           RETURNING id, name, created_at, updated_at""",
        name.strip(), project_id, user_id
    )
    if row:
        # Get counts
        counts = await fetchrow(
            """SELECT
                  (SELECT COUNT(*) FROM project_files WHERE project_id = $1) as file_count,
                  (SELECT COUNT(*) FROM conversations WHERE project_id = $1 AND NOT is_deleted) as conversation_count""",
            project_id
        )
        assert counts is not None, "Aggregate query should always return a row"
        return ProjectDetail(
            id=row["id"],
            name=row["name"],
            creator_name=username,
            file_count=counts["file_count"],
            conversation_count=counts["conversation_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    return None


async def delete_project(project_id: UUID, user_id: UUID) -> bool:
    """Soft delete a project and clean up associated files.

    Side effects:
    - Conversations linked to this project will have project_id set to NULL (ON DELETE SET NULL)
    - Project files will be cascade deleted from DB (ON DELETE CASCADE)
    - Physical files need to be cleaned up separately
    """
    # Get project to verify ownership and get info for file cleanup
    project = await get_project(project_id, user_id)
    if not project:
        return False

    # Get file paths before deletion for cleanup
    file_paths = await fetch(
        "SELECT storage_path FROM project_files WHERE project_id = $1",
        project_id
    )

    # Soft delete the project (cascade handles DB records)
    result = await execute(
        """UPDATE projects
           SET is_deleted = TRUE
           WHERE id = $1 AND user_id = $2 AND NOT is_deleted""",
        project_id, user_id
    )

    if "UPDATE 1" in result:
        # Clean up physical files
        await _cleanup_project_files(user_id, project_id, file_paths)
        return True
    return False


async def _cleanup_project_files(user_id: UUID, project_id: UUID, file_paths: list) -> None:  # type: ignore[type-arg]
    """Clean up physical files for a deleted project."""
    from backend.core.storage import get_project_files_dir
    base_dir = str(get_project_files_dir())
    project_dir = os.path.join(base_dir, str(user_id), str(project_id))

    try:
        if os.path.exists(project_dir):
            shutil.rmtree(project_dir)
    except Exception:
        pass  # Log warning in production


async def check_project_name_exists(user_id: UUID, name: str, exclude_id: UUID | None = None) -> bool:
    """Check if a project name already exists for this user."""
    if exclude_id:
        row = await fetchrow(
            """SELECT 1 FROM projects
               WHERE user_id = $1 AND name = $2 AND id != $3 AND NOT is_deleted""",
            user_id, name.strip(), exclude_id
        )
    else:
        row = await fetchrow(
            """SELECT 1 FROM projects
               WHERE user_id = $1 AND name = $2 AND NOT is_deleted""",
            user_id, name.strip()
        )
    return row is not None


async def check_project_ownership(project_id: UUID, user_id: UUID) -> bool:
    """Check if a project belongs to a user."""
    row = await fetchrow(
        "SELECT 1 FROM projects WHERE id = $1 AND user_id = $2 AND NOT is_deleted",
        project_id, user_id
    )
    return row is not None


# =============================================================================
# Project File Operations
# =============================================================================


async def list_project_files(project_id: UUID) -> list[ProjectFileSummary]:
    """List all files in a project."""
    rows = await fetch(
        """SELECT id, file_id, original_name, content_type, size_bytes, created_at
           FROM project_files
           WHERE project_id = $1
           ORDER BY created_at DESC""",
        project_id
    )
    return [
        ProjectFileSummary(
            id=row["id"],
            file_id=row["file_id"],
            original_name=row["original_name"],
            content_type=row["content_type"],
            size_bytes=row["size_bytes"],
            created_at=row["created_at"],
            download_url=f"/api/projects/{project_id}/files/{row['file_id']}/download",
        )
        for row in rows
    ]


async def create_project_file(
    project_id: UUID,
    file_id: str,
    storage_path: str,
    original_name: str,
    content_type: str | None,
    size_bytes: int,
) -> ProjectFileSummary:
    """Create a new project file record."""
    row = await fetchrow(
        """INSERT INTO project_files (project_id, file_id, storage_path, original_name, content_type, size_bytes)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING id, file_id, original_name, content_type, size_bytes, created_at""",
        project_id, file_id, storage_path, original_name, content_type, size_bytes
    )
    assert row is not None, "INSERT should always return a row"
    return ProjectFileSummary(
        id=row["id"],
        file_id=row["file_id"],
        original_name=row["original_name"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        created_at=row["created_at"],
        download_url=f"/api/projects/{project_id}/files/{row['file_id']}/download",
    )


async def get_project_file(project_id: UUID, file_id: str) -> dict | None:
    """Get a project file record."""
    row = await fetchrow(
        """SELECT id, file_id, storage_path, original_name, content_type, size_bytes, created_at
           FROM project_files
           WHERE project_id = $1 AND file_id = $2""",
        project_id, file_id
    )
    if row:
        return dict(row)
    return None


async def delete_project_file(project_id: UUID, file_id: str) -> str | None:
    """Delete a project file record and return storage path for cleanup."""
    row = await fetchrow(
        """DELETE FROM project_files
           WHERE project_id = $1 AND file_id = $2
           RETURNING storage_path""",
        project_id, file_id
    )
    if row:
        return row["storage_path"]
    return None


async def count_project_files(project_id: UUID) -> int:
    """Count files in a project."""
    row = await fetchrow(
        "SELECT COUNT(*) as count FROM project_files WHERE project_id = $1",
        project_id
    )
    return row["count"] if row else 0


async def check_file_name_exists(project_id: UUID, filename: str, exclude_file_id: str | None = None) -> bool:
    """Check if a filename already exists in the project."""
    if exclude_file_id:
        row = await fetchrow(
            "SELECT 1 FROM project_files WHERE project_id = $1 AND original_name = $2 AND file_id != $3",
            project_id, filename, exclude_file_id
        )
    else:
        row = await fetchrow(
            "SELECT 1 FROM project_files WHERE project_id = $1 AND original_name = $2",
            project_id, filename
        )
    return row is not None


async def rename_project_file(project_id: UUID, file_id: str, new_name: str) -> ProjectFileSummary | None:
    """Rename a project file and update storage path."""
    # Get current file info
    file_record = await get_project_file(project_id, file_id)
    if not file_record:
        return None

    old_storage_path = file_record["storage_path"]
    old_dir = os.path.dirname(old_storage_path)
    new_storage_path = os.path.join(old_dir, new_name)

    # Rename physical file
    if os.path.exists(old_storage_path):
        os.rename(old_storage_path, new_storage_path)

    # Update database
    row = await fetchrow(
        """UPDATE project_files
           SET original_name = $1, storage_path = $2
           WHERE project_id = $3 AND file_id = $4
           RETURNING id, file_id, original_name, content_type, size_bytes, created_at""",
        new_name, new_storage_path, project_id, file_id
    )
    if row:
        return ProjectFileSummary(
            id=row["id"],
            file_id=row["file_id"],
            original_name=row["original_name"],
            content_type=row["content_type"],
            size_bytes=row["size_bytes"],
            created_at=row["created_at"],
            download_url=f"/api/projects/{project_id}/files/{row['file_id']}/download",
        )
    return None


# =============================================================================
# Project Conversation Operations
# =============================================================================


async def list_project_conversations(project_id: UUID) -> list[ProjectConversationSummary]:
    """List all conversations in a project."""
    rows = await fetch(
        """SELECT id, title, updated_at
           FROM conversations
           WHERE project_id = $1 AND NOT is_deleted
           ORDER BY updated_at DESC""",
        project_id
    )
    return [
        ProjectConversationSummary(
            id=row["id"],
            title=row["title"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]
