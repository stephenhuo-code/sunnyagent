"""Unit tests for FileService."""

from __future__ import annotations

from pathlib import Path

import pytest

from meta_agent.services.file_service import (
    FileService,
    PathNotAllowedError,
    PluginNotFoundError,
)


class TestFileService:
    """Tests for FileService."""

    @pytest.fixture
    def service(self, mock_repo_root: Path) -> FileService:
        """Create a file service instance."""
        return FileService(str(mock_repo_root))

    def test_is_allowed_path_valid(self, service: FileService, mock_repo_root: Path):
        """Test valid path is allowed."""
        path = mock_repo_root / "packages" / "test-plugin" / "commands" / "test.md"
        assert service.is_allowed_path(str(path))

    def test_is_allowed_path_outside_packages(self, service: FileService, mock_repo_root: Path):
        """Test path outside packages is not allowed."""
        path = mock_repo_root / "backend" / "main.py"
        assert not service.is_allowed_path(str(path))

    def test_is_allowed_path_parent_traversal(self, service: FileService, mock_repo_root: Path):
        """Test parent traversal is not allowed."""
        path = mock_repo_root / "packages" / ".." / "backend" / "main.py"
        assert not service.is_allowed_path(str(path))

    def test_validate_path_success(self, service: FileService, mock_repo_root: Path):
        """Test path validation success."""
        path = mock_repo_root / "packages" / "test-plugin" / "commands" / "test.md"
        result = service.validate_path(str(path))
        assert "packages" in result
        assert "test-plugin" in result

    def test_validate_path_wrong_extension(self, service: FileService, mock_repo_root: Path):
        """Test validation fails for wrong extension."""
        path = mock_repo_root / "packages" / "test-plugin" / "file.py"
        with pytest.raises(PathNotAllowedError) as exc_info:
            service.validate_path(str(path))
        assert ".py" in str(exc_info.value)

    def test_read_file_success(self, service: FileService, mock_repo_root: Path):
        """Test reading a file."""
        content = service.read_file(
            f"packages/test-plugin/commands/test-command.md"
        )
        assert "description:" in content
        assert "test command" in content.lower()

    def test_read_file_not_found(self, service: FileService):
        """Test reading non-existent file."""
        with pytest.raises(FileNotFoundError):
            service.read_file("packages/test-plugin/commands/missing.md")

    def test_read_command(self, service: FileService):
        """Test reading a command."""
        command = service.read_command("test-plugin", "test-command")
        assert command.name == "test-command"
        assert command.plugin_name == "test-plugin"
        assert command.frontmatter.description == "Test command"

    def test_write_file_success(self, service: FileService, mock_repo_root: Path):
        """Test writing a file."""
        path = "packages/test-plugin/commands/new-command.md"
        content = "---\ndescription: New command\n---\n\nContent"

        service.write_file(path, content)

        # Verify
        full_path = mock_repo_root / path
        assert full_path.exists()
        assert full_path.read_text() == content

    def test_write_file_outside_packages(self, service: FileService):
        """Test writing outside packages fails."""
        with pytest.raises(PathNotAllowedError):
            service.write_file("../backend/hack.py", "bad code")

    def test_list_commands(self, service: FileService):
        """Test listing commands."""
        commands = service.list_commands("test-plugin")
        assert "test-command" in commands

    def test_list_commands_empty_plugin(self, service: FileService):
        """Test listing commands for non-existent plugin."""
        commands = service.list_commands("non-existent")
        assert commands == []

    def test_plugin_exists(self, service: FileService):
        """Test checking if plugin exists."""
        assert service.plugin_exists("test-plugin")
        assert not service.plugin_exists("non-existent")

    def test_ensure_plugin_structure(self, service: FileService, mock_repo_root: Path):
        """Test ensuring plugin structure."""
        service.ensure_plugin_structure("new-plugin")

        plugin_path = mock_repo_root / "packages" / "new-plugin"
        assert plugin_path.exists()
        assert (plugin_path / ".plugin").exists()
        assert (plugin_path / "commands").exists()
        assert (plugin_path / "skills").exists()
        assert (plugin_path / ".plugin" / "plugin.json").exists()

    def test_backup_file(self, service: FileService, mock_repo_root: Path):
        """Test backing up a file."""
        backup_path = service.backup_file(
            "packages/test-plugin/commands/test-command.md"
        )
        assert Path(backup_path).exists()
        assert ".backup." in backup_path

    def test_list_plugins(self, service: FileService):
        """Test listing all plugins."""
        plugins = service.list_plugins()
        assert "test-plugin" in plugins
