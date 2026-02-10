"""Pydantic models for file management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FileCreate(BaseModel):
    """Internal model for creating a file record."""
    file_id: str
    original_name: str
    content_type: str | None = None
    size_bytes: int
    storage_path: str
    conversation_id: UUID | None = None


class FileInfo(BaseModel):
    """File information returned in API responses."""
    id: UUID
    file_id: str
    original_name: str
    content_type: str | None
    size_bytes: int
    created_at: datetime
    download_url: str

    @classmethod
    def from_db_row(cls, row) -> "FileInfo":
        """Create FileInfo from a database row."""
        return cls(
            id=row["id"],
            file_id=row["file_id"],
            original_name=row["original_name"],
            content_type=row["content_type"],
            size_bytes=row["size_bytes"],
            created_at=row["created_at"],
            download_url=f"/api/files/{row['file_id']}/{row['original_name']}"
        )


class FileSummary(BaseModel):
    """Summary of a file for list display."""
    file_id: str
    original_name: str
    size_bytes: int
    created_at: datetime
    download_url: str
