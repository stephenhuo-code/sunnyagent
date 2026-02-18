"""API Contract: Projects Management

This file defines the API contract for the project management feature.
Implementation MUST conform to these specifications.

Feature: 006-project-management
Date: 2026-02-17
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Request Models
# =============================================================================


class ProjectCreate(BaseModel):
    """Request body for creating a new project.

    POST /api/projects
    """

    name: str = Field(..., min_length=1, max_length=100, description="项目名称")


class ProjectUpdate(BaseModel):
    """Request body for updating a project.

    PATCH /api/projects/{project_id}
    """

    name: str = Field(..., min_length=1, max_length=100, description="新项目名称")


class ConversationProjectAssociation(BaseModel):
    """Request body for associating a conversation with a project.

    POST /api/conversations/{conversation_id}/project
    """

    project_id: UUID = Field(..., description="目标项目 ID")


# =============================================================================
# Response Models
# =============================================================================


class ProjectSummary(BaseModel):
    """Summary of a project for list display.

    Used in: GET /api/projects
    """

    id: UUID
    name: str
    file_count: int = Field(description="项目文件数量")
    conversation_count: int = Field(description="项目对话数量")
    created_at: datetime
    updated_at: datetime


class ProjectDetail(BaseModel):
    """Full project details.

    Used in: GET /api/projects/{project_id}
    """

    id: UUID
    name: str
    file_count: int
    conversation_count: int
    created_at: datetime
    updated_at: datetime


class ProjectFileSummary(BaseModel):
    """Summary of a file in a project.

    Used in: GET /api/projects/{project_id}/files
    """

    id: UUID
    file_id: str
    original_name: str
    content_type: str | None
    size_bytes: int
    created_at: datetime
    download_url: str = Field(description="文件下载 URL")


class ProjectConversationSummary(BaseModel):
    """Summary of a conversation in a project.

    Used in: GET /api/projects/{project_id}/conversations
    """

    id: UUID
    title: str
    updated_at: datetime


class FileUploadResponse(BaseModel):
    """Response after uploading a file to a project.

    Used in: POST /api/projects/{project_id}/files
    """

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


# =============================================================================
# API Endpoints Specification
# =============================================================================

"""
## Projects CRUD

### GET /api/projects
获取当前用户的项目列表

Response 200:
    List[ProjectSummary]

Response 401:
    ErrorResponse (未认证)

---

### POST /api/projects
创建新项目

Request Body:
    ProjectCreate

Response 201:
    ProjectDetail

Response 400:
    ErrorResponse (name: "项目名称已存在")

Response 401:
    ErrorResponse (未认证)

---

### GET /api/projects/{project_id}
获取项目详情

Path Parameters:
    project_id: UUID

Response 200:
    ProjectDetail

Response 401:
    ErrorResponse (未认证)

Response 403:
    ErrorResponse (无权限访问该项目)

Response 404:
    ErrorResponse (项目不存在)

---

### PATCH /api/projects/{project_id}
更新项目名称

Path Parameters:
    project_id: UUID

Request Body:
    ProjectUpdate

Response 200:
    ProjectDetail

Response 400:
    ErrorResponse (name: "项目名称已存在")

Response 401:
    ErrorResponse (未认证)

Response 403:
    ErrorResponse (无权限修改该项目)

Response 404:
    ErrorResponse (项目不存在)

---

### DELETE /api/projects/{project_id}
删除项目 (软删除)

Path Parameters:
    project_id: UUID

Response 204:
    (no content)

Response 401:
    ErrorResponse (未认证)

Response 403:
    ErrorResponse (无权限删除该项目)

Response 404:
    ErrorResponse (项目不存在)

Side Effects:
    - 项目关联的文件从存储中删除
    - 项目关联的对话 project_id 设为 NULL

---

## Project Files

### GET /api/projects/{project_id}/files
获取项目文件列表

Path Parameters:
    project_id: UUID

Response 200:
    List[ProjectFileSummary]

Response 401:
    ErrorResponse (未认证)

Response 403:
    ErrorResponse (无权限访问该项目)

Response 404:
    ErrorResponse (项目不存在)

---

### POST /api/projects/{project_id}/files
上传文件到项目

Path Parameters:
    project_id: UUID

Request:
    Content-Type: multipart/form-data
    file: UploadFile (max 10MB)

Response 201:
    FileUploadResponse

Response 400:
    ErrorResponse (code: "FILE_TOO_LARGE", detail: "文件大小不能超过 10MB")
    ErrorResponse (code: "INVALID_FILE_TYPE", detail: "不支持的文件类型")
    ErrorResponse (code: "FILE_LIMIT_EXCEEDED", detail: "项目文件数量已达上限 (50)")
    ErrorResponse (code: "DUPLICATE_FILE_NAME", detail: "文件名已存在")

Response 401:
    ErrorResponse (未认证)

Response 403:
    ErrorResponse (无权限访问该项目)

Response 404:
    ErrorResponse (项目不存在)

---

### DELETE /api/projects/{project_id}/files/{file_id}
删除项目文件

Path Parameters:
    project_id: UUID
    file_id: str

Response 204:
    (no content)

Response 401:
    ErrorResponse (未认证)

Response 403:
    ErrorResponse (无权限访问该项目)

Response 404:
    ErrorResponse (项目或文件不存在)

Side Effects:
    - 从存储中删除物理文件

---

## Project Conversations

### GET /api/projects/{project_id}/conversations
获取项目对话列表

Path Parameters:
    project_id: UUID

Response 200:
    List[ProjectConversationSummary]

Response 401:
    ErrorResponse (未认证)

Response 403:
    ErrorResponse (无权限访问该项目)

Response 404:
    ErrorResponse (项目不存在)

---

### POST /api/conversations/{conversation_id}/project
将对话关联到项目

Path Parameters:
    conversation_id: UUID

Request Body:
    ConversationProjectAssociation

Response 200:
    {"message": "对话已添加到项目"}

Response 400:
    ErrorResponse (detail: "对话已属于该项目")

Response 401:
    ErrorResponse (未认证)

Response 403:
    ErrorResponse (无权限操作该对话或项目)

Response 404:
    ErrorResponse (对话或项目不存在)

---

### DELETE /api/conversations/{conversation_id}/project
移除对话的项目关联

Path Parameters:
    conversation_id: UUID

Response 204:
    (no content)

Response 401:
    ErrorResponse (未认证)

Response 403:
    ErrorResponse (无权限操作该对话)

Response 404:
    ErrorResponse (对话不存在)

"""
