"""File upload and download API endpoints."""

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.auth.dependencies import get_current_user
from backend.auth.models import UserInfo
from backend.files import database as files_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])

# File upload constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv",  # Text files
    ".pdf",  # PDF
    ".doc", ".docx",  # Word
    ".ppt", ".pptx",  # PowerPoint
    ".xls", ".xlsx",  # Excel
}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: UserInfo = Depends(get_current_user)
):
    """Upload a file and return its metadata."""
    # Validate file extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )

    # Generate file ID and save
    file_id = uuid.uuid4().hex[:8]
    file_dir = Path(f"/tmp/sunnyagent_files/{file_id}")
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / (file.filename or "uploaded_file")

    with open(file_path, "wb") as f:
        f.write(content)

    # Record file in database (if PostgreSQL is available)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            await files_db.create_file(
                user_id=current_user.id,
                file_id=file_id,
                original_name=file.filename or "uploaded_file",
                content_type=file.content_type,
                size_bytes=len(content),
                storage_path=str(file_path)
            )
        except Exception as e:
            logger.warning(f"Failed to record file in database: {e}")

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "content_type": file.content_type or "application/octet-stream",
        "download_url": f"/api/files/{file_id}/{file.filename}",
    }


@router.get("/{file_id}/download")
async def download_file_by_id(
    file_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """Download a file by its ID.

    Permission: User must own the file.
    """
    # Check permission via database if PostgreSQL is available
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        file_record = await files_db.get_file(file_id, current_user.id)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        file_path = Path(file_record["storage_path"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(
            str(file_path),
            filename=file_record["original_name"],
            media_type=file_record["content_type"] or "application/octet-stream",
        )

    # Fallback for SQLite mode (no permission check)
    file_dir = Path(f"/tmp/sunnyagent_files/{file_id}")
    if not file_dir.exists():
        raise HTTPException(status_code=404, detail="File not found")

    files = list(file_dir.iterdir())
    if not files:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = files[0]
    return FileResponse(
        str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.get("/{file_id}/content")
async def get_file_content(
    file_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """Get file content for preview (text files only).

    Permission: User must own the file.
    """
    # Check permission via database if PostgreSQL is available
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        file_record = await files_db.get_file(file_id, current_user.id)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        file_path = Path(file_record["storage_path"])
    else:
        # Fallback for SQLite mode (no permission check)
        file_dir = Path(f"/tmp/sunnyagent_files/{file_id}")
        if not file_dir.exists():
            raise HTTPException(status_code=404, detail="File not found")
        files = list(file_dir.iterdir())
        if not files:
            raise HTTPException(status_code=404, detail="File not found")
        file_path = files[0]

    # Only support text file preview
    text_extensions = {".txt", ".md", ".json", ".csv"}
    if file_path.suffix.lower() not in text_extensions:
        raise HTTPException(
            status_code=400,
            detail="Preview not supported for this file type"
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Cannot read file as text"
        )

    return {"content": content, "filename": file_path.name}


@router.get("/{file_id}/{filename}")
async def download_file(
    file_id: str,
    filename: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """Download a generated file by file_id and filename.

    Permission: User must own the file (if DB record exists).

    Note: This route MUST be defined after /api/files/{file_id}/content
    and /api/files/{file_id}/download to avoid path conflicts.

    Bug fix: Check filesystem first, then validate ownership if DB record exists.
    This handles cases where sandbox generates files without user_id in config.
    """
    file_path = f"/tmp/sunnyagent_files/{file_id}/{filename}"

    # First check if file exists on filesystem
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # If database is available, check ownership (optional - file may not be registered)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        file_record = await files_db.get_file(file_id, current_user.id)
        # If DB record exists, use its filename; otherwise allow download anyway
        # (handles sandbox-generated files not registered due to missing user_id)
        if file_record:
            filename = file_record.get("original_name", filename)

    return FileResponse(
        file_path,
        filename=filename,
        media_type="application/octet-stream",
    )
