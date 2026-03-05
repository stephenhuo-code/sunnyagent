"""File service for Plugin file operations."""

from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from meta_agent.models.plugin import Command, CommandFrontmatter, Skill, SkillFrontmatter

logger = logging.getLogger(__name__)


# Configuration
PACKAGES_DIR = "packages"
ALLOWED_EXTENSIONS = [".md", ".json"]


# Exceptions


class FileServiceError(Exception):
    """File service error."""

    pass


class PathNotAllowedError(FileServiceError):
    """Path not in allowed range.

    This is a security-critical error.
    """

    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Path not allowed: {path} - {reason}")


class InvalidPathError(FileServiceError):
    """Invalid path format."""

    pass


class PluginNotFoundError(FileServiceError):
    """Plugin not found."""

    pass


class FileService:
    """File operation service for Plugin files.

    Enforces packages/ directory restriction.
    Only allows .md and .json files.
    """

    def __init__(self, repo_root: str):
        """
        Initialize file service.

        Args:
            repo_root: Absolute path to repository root
        """
        self.repo_root = Path(repo_root).resolve()
        self.packages_dir = self.repo_root / PACKAGES_DIR

    # Path Validation

    def is_allowed_path(self, file_path: str) -> bool:
        """
        Check if path is within allowed range.

        Args:
            file_path: Relative or absolute path

        Returns:
            Whether operation is allowed
        """
        try:
            self.validate_path(file_path)
            return True
        except (PathNotAllowedError, InvalidPathError):
            return False

    def validate_path(self, file_path: str) -> str:
        """
        Validate and normalize path.

        Args:
            file_path: File path

        Returns:
            Normalized absolute path

        Raises:
            PathNotAllowedError: Path not within packages/
            InvalidPathError: Invalid path format
        """
        # Convert to absolute path
        if os.path.isabs(file_path):
            abs_path = Path(file_path)
        else:
            abs_path = (self.repo_root / file_path).resolve()

        # Resolve symlinks
        try:
            real_path = abs_path.resolve()
        except (OSError, ValueError) as e:
            raise InvalidPathError(f"Cannot resolve path: {file_path}") from e

        # Check if within packages/ directory
        try:
            real_path.relative_to(self.packages_dir)
        except ValueError:
            raise PathNotAllowedError(
                file_path,
                f"Path must be within {self.packages_dir}",
            )

        # Check extension
        ext = real_path.suffix.lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            raise PathNotAllowedError(
                file_path,
                f"Extension {ext} not allowed, must be one of {ALLOWED_EXTENSIONS}",
            )

        return str(real_path)

    # Read Operations

    def read_file(self, file_path: str) -> str:
        """
        Read file content.

        Args:
            file_path: File path

        Returns:
            File content

        Raises:
            FileNotFoundError: File doesn't exist
            PathNotAllowedError: Path not allowed
        """
        validated_path = self.validate_path(file_path)

        if not os.path.exists(validated_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(validated_path, "r", encoding="utf-8") as f:
            return f.read()

    def read_command(self, plugin_name: str, command_name: str) -> Command:
        """
        Read Command definition.

        Args:
            plugin_name: Plugin name
            command_name: Command name

        Returns:
            Command object
        """
        file_path = f"{PACKAGES_DIR}/{plugin_name}/commands/{command_name}.md"
        content = self.read_file(file_path)
        return Command.from_markdown(
            content=content,
            name=command_name,
            plugin_name=plugin_name,
            file_path=file_path,
        )

    def read_skill(self, plugin_name: str, skill_name: str) -> Skill:
        """
        Read Skill definition.

        Args:
            plugin_name: Plugin name
            skill_name: Skill name

        Returns:
            Skill object
        """
        file_path = f"{PACKAGES_DIR}/{plugin_name}/skills/{skill_name}/SKILL.md"
        content = self.read_file(file_path)

        references_dir = f"{PACKAGES_DIR}/{plugin_name}/skills/{skill_name}/references"
        if not os.path.isdir(self.repo_root / references_dir):
            references_dir = None

        return Skill.from_markdown(
            content=content,
            name=skill_name,
            plugin_name=plugin_name,
            file_path=file_path,
            references_dir=references_dir,
        )

    def list_commands(self, plugin_name: str) -> list[str]:
        """List all Commands in Plugin."""
        commands_dir = self.packages_dir / plugin_name / "commands"
        if not commands_dir.exists():
            return []

        commands = []
        for f in commands_dir.glob("*.md"):
            commands.append(f.stem)
        return sorted(commands)

    def list_skills(self, plugin_name: str) -> list[str]:
        """List all Skills in Plugin."""
        skills_dir = self.packages_dir / plugin_name / "skills"
        if not skills_dir.exists():
            return []

        skills = []
        for d in skills_dir.iterdir():
            if d.is_dir() and (d / "SKILL.md").exists():
                skills.append(d.name)
        return sorted(skills)

    # Write Operations

    def write_file(
        self,
        file_path: str,
        content: str,
        create_dirs: bool = True,
    ) -> None:
        """
        Write file.

        Args:
            file_path: File path
            content: File content
            create_dirs: Whether to auto-create directories

        Raises:
            PathNotAllowedError: Path not within packages/
        """
        validated_path = self.validate_path(file_path)

        if create_dirs:
            os.makedirs(os.path.dirname(validated_path), exist_ok=True)

        with open(validated_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Wrote file: {file_path}")
        self._audit_log("write_file", file_path, "success")

    def write_command(self, plugin_name: str, command: Command) -> str:
        """
        Write Command definition.

        Returns:
            Written file path
        """
        file_path = f"{PACKAGES_DIR}/{plugin_name}/commands/{command.name}.md"
        content = command.to_markdown()
        self.write_file(file_path, content)
        return file_path

    def write_skill(self, plugin_name: str, skill: Skill) -> str:
        """
        Write Skill definition.

        Returns:
            Written file path
        """
        file_path = f"{PACKAGES_DIR}/{plugin_name}/skills/{skill.name}/SKILL.md"
        content = skill.to_markdown()
        self.write_file(file_path, content)
        return file_path

    def backup_file(self, file_path: str) -> str:
        """
        Backup file.

        Returns:
            Backup file path
        """
        validated_path = self.validate_path(file_path)

        if not os.path.exists(validated_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{validated_path}.backup.{timestamp}"
        shutil.copy2(validated_path, backup_path)

        logger.info(f"Backed up {file_path} to {backup_path}")
        return backup_path

    # Directory Operations

    def ensure_plugin_structure(self, plugin_name: str) -> None:
        """
        Ensure Plugin directory structure exists.

        Creates:
            packages/{plugin}/
            packages/{plugin}/.plugin/
            packages/{plugin}/commands/
            packages/{plugin}/skills/
        """
        plugin_path = self.packages_dir / plugin_name

        dirs_to_create = [
            plugin_path,
            plugin_path / ".plugin",
            plugin_path / "commands",
            plugin_path / "skills",
        ]

        for d in dirs_to_create:
            d.mkdir(parents=True, exist_ok=True)

        # Create plugin.json if not exists
        plugin_json = plugin_path / ".plugin" / "plugin.json"
        if not plugin_json.exists():
            import json

            plugin_json.write_text(
                json.dumps(
                    {
                        "name": plugin_name,
                        "version": "0.1.0",
                        "description": "",
                    },
                    indent=2,
                )
            )

        logger.info(f"Ensured plugin structure for: {plugin_name}")

    def plugin_exists(self, plugin_name: str) -> bool:
        """Check if Plugin exists."""
        plugin_path = self.packages_dir / plugin_name
        return plugin_path.is_dir()

    def get_plugin_path(self, plugin_name: str) -> str:
        """Get Plugin directory path."""
        return str(self.packages_dir / plugin_name)

    def list_plugins(self) -> list[str]:
        """List all plugins."""
        if not self.packages_dir.exists():
            return []

        plugins = []
        for d in self.packages_dir.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                plugins.append(d.name)
        return sorted(plugins)

    # Audit Logging

    def _audit_log(
        self,
        operation: str,
        path: str,
        result: str,
    ) -> None:
        """Record operation to audit log."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "path": path,
            "user": "meta-agent",
            "result": result,
        }
        logger.debug(f"Audit: {log_entry}")
