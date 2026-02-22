"""Pydantic models for plugin management API."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class PluginSource(str, Enum):
    """Plugin source types."""

    PRESET = "preset"
    PACKAGE = "package"
    UPLOADED = "uploaded"
    SHARED = "shared"


class PluginType(str, Enum):
    """Plugin types."""

    AGENT = "agent"
    SKILL = "skill"


class SkillType(str, Enum):
    """Skill execution types."""

    ATOMIC = "atomic"
    WORKFLOW = "workflow"


# =============================================================================
# Nested Models
# =============================================================================


class SkillStepInfo(BaseModel):
    """A single step in a workflow skill."""

    id: str
    description: str
    required_capability: str | None = None


class PluginRatingInfo(BaseModel):
    """Plugin rating summary."""

    average: float = Field(ge=0, le=5)
    count: int = Field(ge=0)


# =============================================================================
# Main Models
# =============================================================================


class PluginInfo(BaseModel):
    """Unified plugin information model for API responses."""

    # Core fields (required)
    name: str  # Namespaced format: {source}:{name}
    display_name: str
    type: PluginType
    source: PluginSource
    description: str
    version: str
    enabled: bool  # Current user's enabled state

    # Optional metadata
    author: str | None = None

    # Agent-specific fields
    capabilities: list[str] | None = None
    commands: list[str] | None = None  # /command list
    skills: list["PluginInfo"] | None = None  # Nested skills

    # Skill-specific fields
    skill_type: SkillType | None = None
    steps: list[SkillStepInfo] | None = None

    # Rating (Package/Shared only)
    rating: PluginRatingInfo | None = None

    # Upload/Share related
    uploader_id: UUID | None = None
    uploader_name: str | None = None
    is_delisted: bool = False


# =============================================================================
# Request/Response Models
# =============================================================================


class PluginStateUpdateRequest(BaseModel):
    """Request to update plugin enabled state."""

    enabled: bool


class PluginRatingRequest(BaseModel):
    """Request to rate a plugin."""

    rating: int = Field(ge=1, le=5)


class PluginUploadResponse(BaseModel):
    """Response after plugin upload."""

    success: bool
    plugin: PluginInfo
    warnings: list[str] | None = None


class PluginListResponse(BaseModel):
    """Response containing list of plugins."""

    plugins: list[PluginInfo]


# =============================================================================
# Database Models (for internal use)
# =============================================================================


class UserPluginState(BaseModel):
    """User's plugin state from database."""

    id: UUID
    user_id: UUID
    plugin_name: str  # Namespaced format
    enabled: bool
    created_at: datetime
    updated_at: datetime


class UploadedPlugin(BaseModel):
    """Uploaded plugin record from database."""

    id: UUID
    user_id: UUID
    plugin_name: str
    plugin_type: PluginType
    display_name: str
    description: str | None = None
    version: str = "1.0.0"
    author: str | None = None
    storage_path: str
    is_shared: bool = False
    is_delisted: bool = False
    created_at: datetime
    updated_at: datetime


class PluginRating(BaseModel):
    """Plugin rating record from database."""

    id: UUID
    user_id: UUID
    plugin_name: str  # Namespaced format
    rating: int
    created_at: datetime
    updated_at: datetime
