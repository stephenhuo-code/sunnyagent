"""Pydantic models for project management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Request Models
# =============================================================================


class ProjectCreate(BaseModel):
    """Request body for creating a new project."""

    name: str = Field(..., min_length=1, max_length=100, description="项目名称")


class ProjectUpdate(BaseModel):
    """Request body for updating a project."""

    name: str = Field(..., min_length=1, max_length=100, description="新项目名称")


class ConversationProjectAssociation(BaseModel):
    """Request body for associating a conversation with a project."""

    project_id: UUID = Field(..., description="目标项目 ID")


class FileRename(BaseModel):
    """Request body for renaming a file."""

    name: str = Field(..., min_length=1, max_length=255, description="新文件名")


# =============================================================================
# Response Models
# =============================================================================


class ProjectSummary(BaseModel):
    """Summary of a project for list display."""

    id: UUID
    name: str
    creator_name: str = Field(description="创建者用户名")
    file_count: int = Field(description="项目文件数量")
    conversation_count: int = Field(description="项目对话数量")
    created_at: datetime
    updated_at: datetime


class ProjectDetail(BaseModel):
    """Full project details."""

    id: UUID
    name: str
    creator_name: str = Field(description="创建者用户名")
    file_count: int
    conversation_count: int
    created_at: datetime
    updated_at: datetime


class ProjectFileSummary(BaseModel):
    """Summary of a file in a project."""

    id: UUID
    file_id: str
    original_name: str
    content_type: str | None
    size_bytes: int
    created_at: datetime
    download_url: str = Field(description="文件下载 URL")


class ProjectConversationSummary(BaseModel):
    """Summary of a conversation in a project."""

    id: UUID
    title: str
    updated_at: datetime


class FileUploadResponse(BaseModel):
    """Response after uploading a file to a project."""

    id: UUID
    file_id: str
    original_name: str
    content_type: str | None
    size_bytes: int
    download_url: str


# =============================================================================
# Error Response Models
# =============================================================================


class ErrorResponse(BaseModel):
    """Standard error response format."""

    detail: str = Field(description="错误描述")
    code: str | None = Field(default=None, description="错误代码")
