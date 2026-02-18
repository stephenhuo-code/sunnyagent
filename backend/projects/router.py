"""API router for project management."""

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse

from backend.auth.dependencies import get_current_user
from backend.auth.models import UserInfo
from backend.projects.models import (
    ProjectCreate,
    ProjectUpdate,
    ProjectDetail,
    ProjectSummary,
    ProjectFileSummary,
    ProjectConversationSummary,
    FileUploadResponse,
    FileRename,
)
from backend.projects import database as db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


# =============================================================================
# File Upload Configuration
# =============================================================================

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FILES_PER_PROJECT = 50

ALLOWED_CONTENT_TYPES = {
    # Documents
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    # Code files (mapped from extensions)
    "text/x-python",
    "text/javascript",
    "text/typescript",
    "application/javascript",
    "application/typescript",
}

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".txt", ".md", ".csv", ".json",
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".c", ".cpp", ".h", ".hpp",
    ".rs", ".rb", ".php", ".swift", ".kt",
}


def _get_project_files_base_dir() -> str:
    """Get the base directory for project files."""
    return os.getenv("PROJECT_FILES_DIR", "/tmp/sunnyagent_project_files")


def _validate_file_extension(filename: str) -> bool:
    """Check if file extension is allowed."""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


# =============================================================================
# Project CRUD Endpoints
# =============================================================================


@router.get("", response_model=list[ProjectSummary])
async def list_projects(
    current_user: UserInfo = Depends(get_current_user)
) -> list[ProjectSummary]:
    """List all projects for the current user."""
    return await db.list_user_projects(current_user.id)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectDetail)
async def create_project(
    body: ProjectCreate,
    current_user: UserInfo = Depends(get_current_user)
) -> ProjectDetail:
    """Create a new project."""
    # Check for duplicate name
    if await db.check_project_name_exists(current_user.id, body.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目名称已存在"
        )

    return await db.create_project(current_user.id, body.name, current_user.username)


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: uuid.UUID,
    current_user: UserInfo = Depends(get_current_user)
) -> ProjectDetail:
    """Get a project by ID."""
    project = await db.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    return project


@router.patch("/{project_id}", response_model=ProjectDetail)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    current_user: UserInfo = Depends(get_current_user)
) -> ProjectDetail:
    """Update a project's name."""
    # Check ownership
    if not await db.check_project_ownership(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    # Check for duplicate name (excluding current project)
    if await db.check_project_name_exists(current_user.id, body.name, exclude_id=project_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目名称已存在"
        )

    project = await db.update_project(project_id, current_user.id, body.name, current_user.username)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    current_user: UserInfo = Depends(get_current_user)
) -> None:
    """Delete a project (soft delete).

    Side effects:
    - Project files are deleted from storage
    - Conversations are unlinked (not deleted)
    """
    deleted = await db.delete_project(project_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )


# =============================================================================
# Project Files Endpoints
# =============================================================================


@router.get("/{project_id}/files", response_model=list[ProjectFileSummary])
async def list_project_files(
    project_id: uuid.UUID,
    current_user: UserInfo = Depends(get_current_user)
) -> list[ProjectFileSummary]:
    """List all files in a project."""
    # Check ownership
    if not await db.check_project_ownership(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    return await db.list_project_files(project_id)


@router.post("/{project_id}/files", status_code=status.HTTP_201_CREATED, response_model=FileUploadResponse)
async def upload_project_file(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: UserInfo = Depends(get_current_user)
) -> FileUploadResponse:
    """Upload a file to a project."""
    # Check ownership
    if not await db.check_project_ownership(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    # Check file count limit
    file_count = await db.count_project_files(project_id)
    if file_count >= MAX_FILES_PER_PROJECT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"项目文件数量已达上限 ({MAX_FILES_PER_PROJECT})"
        )

    # Validate file extension
    filename = file.filename or "uploaded_file"
    if not _validate_file_extension(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件类型"
        )

    # Check for duplicate filename
    if await db.check_file_name_exists(project_id, filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名已存在"
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小不能超过 {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )

    # Generate file ID and save
    file_id = uuid.uuid4().hex[:12]
    base_dir = _get_project_files_base_dir()
    file_dir = Path(base_dir) / str(current_user.id) / str(project_id)
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / filename

    with open(file_path, "wb") as f:
        f.write(content)

    # Create database record
    file_record = await db.create_project_file(
        project_id=project_id,
        file_id=file_id,
        storage_path=str(file_path),
        original_name=filename,
        content_type=file.content_type,
        size_bytes=len(content),
    )

    return FileUploadResponse(
        id=file_record.id,
        file_id=file_id,
        original_name=filename,
        content_type=file.content_type,
        size_bytes=len(content),
        download_url=f"/api/projects/{project_id}/files/{file_id}/download",
    )


@router.patch("/{project_id}/files/{file_id}", response_model=ProjectFileSummary)
async def rename_project_file(
    project_id: uuid.UUID,
    file_id: str,
    body: FileRename,
    current_user: UserInfo = Depends(get_current_user)
) -> ProjectFileSummary:
    """Rename a file in a project."""
    # Check ownership
    if not await db.check_project_ownership(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    # Validate file extension
    if not _validate_file_extension(body.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件类型"
        )

    # Check for duplicate filename (excluding current file)
    if await db.check_file_name_exists(project_id, body.name, exclude_file_id=file_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名已存在"
        )

    # Rename file
    result = await db.rename_project_file(project_id, file_id, body.name)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    return result


@router.delete("/{project_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_file(
    project_id: uuid.UUID,
    file_id: str,
    current_user: UserInfo = Depends(get_current_user)
) -> None:
    """Delete a file from a project."""
    # Check ownership
    if not await db.check_project_ownership(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    # Delete from database and get storage path
    storage_path = await db.delete_project_file(project_id, file_id)
    if not storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )

    # Delete physical file
    try:
        if os.path.exists(storage_path):
            os.remove(storage_path)
    except Exception as e:
        logger.warning(f"Failed to delete file {storage_path}: {e}")


@router.get("/{project_id}/files/{file_id}/download")
async def download_project_file(
    project_id: uuid.UUID,
    file_id: str,
    current_user: UserInfo = Depends(get_current_user)
) -> FileResponse:
    """Download a project file."""
    # Check ownership
    if not await db.check_project_ownership(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    # Get file record
    file_record = await db.get_project_file(project_id, file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )

    # Check physical file exists
    storage_path = file_record["storage_path"]
    if not os.path.exists(storage_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )

    return FileResponse(
        storage_path,
        filename=file_record["original_name"],
        media_type=file_record["content_type"] or "application/octet-stream",
    )


# =============================================================================
# Project Conversations Endpoints
# =============================================================================


@router.get("/{project_id}/conversations", response_model=list[ProjectConversationSummary])
async def list_project_conversations(
    project_id: uuid.UUID,
    current_user: UserInfo = Depends(get_current_user)
) -> list[ProjectConversationSummary]:
    """List all conversations in a project."""
    # Check ownership
    if not await db.check_project_ownership(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    return await db.list_project_conversations(project_id)
