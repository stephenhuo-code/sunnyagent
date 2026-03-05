"""Dataset models for test cases and datasets."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Message(BaseModel):
    """Conversation message."""

    role: Literal["user", "assistant"]
    content: str


class ProjectConfig(BaseModel):
    """Test project configuration."""

    name: str = "meta-agent-test"
    reuse: bool = True
    cleanup: bool = False


class TestCase(BaseModel):
    """Single test case."""

    # Identity
    case_id: str = Field(..., description="Unique identifier, e.g., 'qc_001'")

    # Input
    input: str = Field(..., description="User input message")
    context_files: list[str] = Field(
        default_factory=list,
        description="Files to select as context (relative to test-resources/files/)",
    )
    conversation_history: list[Message] = Field(
        default_factory=list,
        description="Multi-turn conversation history",
    )

    # Expected
    command: str | None = Field(
        default=None,
        description="Command name (metadata for grouping)",
    )
    expected_skill: str | None = Field(
        default=None,
        description="Expected skill to be triggered",
    )
    expected_output_contains: list[str] = Field(
        default_factory=list,
        description="Keywords expected in output",
    )
    expected_behavior: str = Field(
        ...,
        description="Natural language description of expected behavior (for LLM evaluation)",
    )

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Tags for filtering")
    project_config: ProjectConfig | None = None

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, v: str) -> str:
        """Validate case_id format."""
        if not v or not v.strip():
            raise ValueError("case_id cannot be empty")
        return v.strip()

    @field_validator("input")
    @classmethod
    def validate_input(cls, v: str) -> str:
        """Validate input is not empty."""
        if not v or not v.strip():
            raise ValueError("input cannot be empty")
        return v

    @field_validator("expected_behavior")
    @classmethod
    def validate_expected_behavior(cls, v: str) -> str:
        """Validate expected_behavior is not empty."""
        if not v or not v.strip():
            raise ValueError("expected_behavior cannot be empty")
        return v


class TestFile(BaseModel):
    """Test file information."""

    # Identity
    relative_path: str = Field(
        ...,
        description="Relative path (relative to test-resources/files/)",
    )

    # Content
    file_size: int = Field(default=0, description="File size in bytes")
    file_type: str = Field(default="", description="File type (csv, xlsx, pdf, etc.)")

    # Upload tracking
    uploaded_to_project: str | None = Field(
        default=None,
        description="Project name where file was uploaded",
    )
    sunnyagent_file_id: str | None = Field(
        default=None,
        description="File ID in SunnyAgent",
    )

    def absolute_path(self, base_dir: str) -> str:
        """Get absolute path."""
        return os.path.join(base_dir, "test-resources/files", self.relative_path)

    def exists(self, base_dir: str) -> bool:
        """Check if file exists."""
        return os.path.isfile(self.absolute_path(base_dir))


class TestDataset(BaseModel):
    """Test dataset containing multiple test cases."""

    # Identity
    name: str = Field(..., description="Dataset name, e.g., 'qc-plugin-v1'")
    version: str = Field(default="v1", description="Version number")
    plugin_name: str = Field(..., description="Target plugin name")

    # Content
    cases: list[TestCase] = Field(..., description="Test cases")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    source_file: str = Field(default="", description="Source file path (CSV/JSONL)")

    # Langfuse sync
    langfuse_dataset_id: str | None = None
    last_synced_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is kebab-case."""
        if not v:
            raise ValueError("name cannot be empty")
        # Allow alphanumeric, hyphens, and underscores
        import re

        if not re.match(r"^[a-z0-9][a-z0-9\-_]*$", v.lower()):
            raise ValueError(
                "name should be kebab-case (alphanumeric with hyphens/underscores)"
            )
        return v

    @field_validator("cases")
    @classmethod
    def validate_cases(cls, v: list[TestCase]) -> list[TestCase]:
        """Validate at least one case exists and case_ids are unique."""
        if not v:
            raise ValueError("Dataset must contain at least one test case")

        case_ids = [c.case_id for c in v]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("case_id must be unique within dataset")

        return v

    def get_all_context_files(self) -> set[str]:
        """Get all unique context files from all cases."""
        files: set[str] = set()
        for case in self.cases:
            files.update(case.context_files)
        return files

    def increment_version(self) -> None:
        """Increment version number (v1 -> v2)."""
        if self.version.startswith("v"):
            try:
                num = int(self.version[1:])
                self.version = f"v{num + 1}"
            except ValueError:
                self.version = "v1"
        else:
            self.version = "v1"
        self.updated_at = datetime.now()
