"""Plugin schema models for Command and Skill."""

from __future__ import annotations

import yaml
from pydantic import BaseModel, Field


class CommandFrontmatter(BaseModel):
    """Command file YAML frontmatter."""

    description: str = Field(..., description="Command description")
    allowed_tools: str | None = None
    argument_hint: str | None = None
    skills: list[str] = Field(default_factory=list)


class Command(BaseModel):
    """Command definition."""

    # Identity
    name: str = Field(..., description="Command name (from filename)")
    plugin_name: str = Field(..., description="Parent plugin name")

    # Content
    frontmatter: CommandFrontmatter
    content: str = Field(default="", description="Markdown body")

    # File info
    file_path: str = Field(default="", description="Relative path to packages/")

    def to_markdown(self) -> str:
        """Generate Markdown file content."""
        yaml_content = yaml.dump(
            self.frontmatter.model_dump(exclude_none=True),
            allow_unicode=True,
            default_flow_style=False,
        )
        return f"---\n{yaml_content}---\n\n{self.content}"

    @classmethod
    def from_markdown(
        cls,
        content: str,
        name: str,
        plugin_name: str,
        file_path: str = "",
    ) -> "Command":
        """Parse Command from Markdown content."""
        # Split frontmatter and body
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                yaml_content = parts[1].strip()
                body = parts[2].strip()
                frontmatter_data = yaml.safe_load(yaml_content) or {}
            else:
                frontmatter_data = {}
                body = content
        else:
            frontmatter_data = {}
            body = content

        return cls(
            name=name,
            plugin_name=plugin_name,
            frontmatter=CommandFrontmatter(**frontmatter_data),
            content=body,
            file_path=file_path,
        )


class SkillFrontmatter(BaseModel):
    """Skill file YAML frontmatter."""

    name: str = Field(..., description="Skill name")
    description: str = Field(..., description="Skill description")


class Skill(BaseModel):
    """Skill definition."""

    # Identity
    name: str = Field(..., description="Skill name")
    plugin_name: str = Field(..., description="Parent plugin name")

    # Content
    frontmatter: SkillFrontmatter
    content: str = Field(default="", description="Markdown body")

    # File info
    file_path: str = Field(default="", description="Relative path to packages/")
    references_dir: str | None = Field(
        default=None,
        description="References directory path",
    )

    def to_markdown(self) -> str:
        """Generate Markdown file content."""
        yaml_content = yaml.dump(
            self.frontmatter.model_dump(),
            allow_unicode=True,
            default_flow_style=False,
        )
        return f"---\n{yaml_content}---\n\n{self.content}"

    @classmethod
    def from_markdown(
        cls,
        content: str,
        name: str,
        plugin_name: str,
        file_path: str = "",
        references_dir: str | None = None,
    ) -> "Skill":
        """Parse Skill from Markdown content."""
        # Split frontmatter and body
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                yaml_content = parts[1].strip()
                body = parts[2].strip()
                frontmatter_data = yaml.safe_load(yaml_content) or {}
            else:
                frontmatter_data = {"name": name, "description": ""}
                body = content
        else:
            frontmatter_data = {"name": name, "description": ""}
            body = content

        # Ensure required fields
        if "name" not in frontmatter_data:
            frontmatter_data["name"] = name
        if "description" not in frontmatter_data:
            frontmatter_data["description"] = ""

        return cls(
            name=name,
            plugin_name=plugin_name,
            frontmatter=SkillFrontmatter(**frontmatter_data),
            content=body,
            file_path=file_path,
            references_dir=references_dir,
        )
