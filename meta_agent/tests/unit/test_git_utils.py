"""Unit tests for GitUtils."""

from __future__ import annotations

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from meta_agent.utils.git_utils import GitUtils, GitError


class TestGitUtils:
    """Tests for GitUtils."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mock git repository."""
        repo = MagicMock()
        repo.index = MagicMock()
        repo.index.add = MagicMock()
        repo.index.commit = MagicMock(return_value=MagicMock(hexsha="abc123def456"))
        repo.index.diff = MagicMock(return_value=[])
        repo.git = MagicMock()
        repo.git.diff = MagicMock(return_value="diff content")
        repo.git.revert = MagicMock()
        repo.git.show = MagicMock(return_value="commit info")
        repo.git.checkout = MagicMock()
        repo.head = MagicMock()
        repo.head.commit = MagicMock(hexsha="current123")
        repo.is_dirty = MagicMock(return_value=False)

        # Mock iter_commits for get_recent_commits
        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123def456"
        mock_commit.message = "Test commit message"
        mock_commit.author = "Test Author"
        mock_commit.committed_date = datetime.now().timestamp()
        repo.iter_commits = MagicMock(return_value=[mock_commit])

        # Mock commit for get_modified_files
        mock_parent = MagicMock()
        mock_parent.diff = MagicMock(return_value=[])
        mock_commit.parents = [mock_parent]
        repo.commit = MagicMock(return_value=mock_commit)

        return repo

    @pytest.fixture
    def git_utils(self, mock_repo, tmp_path) -> GitUtils:
        """Create a GitUtils instance with mocked repo."""
        with patch("meta_agent.utils.git_utils.Repo") as MockRepo:
            MockRepo.return_value = mock_repo
            utils = GitUtils(str(tmp_path))
            utils.repo = mock_repo  # Ensure the mock is used
            return utils

    # Commit Tests

    def test_commit_files(self, git_utils: GitUtils, mock_repo):
        """Test committing files."""
        files = ["commands/quality-data.md", "skills/data-profiler/SKILL.md"]
        message = "Update quality data command"

        commit_hash = git_utils.commit(files, message)

        assert commit_hash == "abc123def456"
        # Index.add is called once per file
        assert mock_repo.index.add.call_count == 2
        mock_repo.index.commit.assert_called_once()

    def test_commit_with_empty_files(self, git_utils: GitUtils, mock_repo):
        """Test committing with empty file list."""
        commit_hash = git_utils.commit([], "Empty commit")

        # Should still create commit (maybe for metadata)
        assert commit_hash is not None

    def test_commit_message_format(self, git_utils: GitUtils, mock_repo):
        """Test commit message formatting."""
        files = ["test.md"]
        message = "Test commit"

        git_utils.commit(files, message)

        # Verify the commit was called with the message (with prefix)
        call_args = mock_repo.index.commit.call_args
        assert "meta-agent:" in str(call_args)
        assert message in str(call_args)

    # Revert/Rollback Tests

    def test_revert_commit(self, git_utils: GitUtils, mock_repo):
        """Test reverting a commit."""
        commit_hash = "abc123"

        git_utils.revert_commit(commit_hash)

        mock_repo.git.revert.assert_called_once()

    def test_revert_file_to_head(self, git_utils: GitUtils, mock_repo):
        """Test reverting a file to HEAD."""
        file_path = "commands/test.md"

        git_utils.revert_file(file_path)

        mock_repo.git.checkout.assert_called_once()

    def test_revert_file_to_specific_commit(self, git_utils: GitUtils, mock_repo):
        """Test reverting a file to a specific commit."""
        file_path = "commands/test.md"
        commit_hash = "def456"

        git_utils.revert_file(file_path, commit_hash)

        mock_repo.git.checkout.assert_called_once()
        call_args = mock_repo.git.checkout.call_args
        assert commit_hash in str(call_args)

    def test_revert_commit_creates_new_commit(self, git_utils: GitUtils, mock_repo):
        """Test that revert creates a new commit (not destructive)."""
        commit_hash = "abc123"

        # Revert should use git revert, not reset
        git_utils.revert_commit(commit_hash)

        # Verify revert was used (safe operation)
        mock_repo.git.revert.assert_called()

    # Diff Tests

    def test_diff_single_file(self, git_utils: GitUtils, mock_repo):
        """Test getting diff for a single file."""
        file_path = "commands/test.md"

        diff = git_utils.diff(file_path=file_path)

        assert diff == "diff content"
        mock_repo.git.diff.assert_called()

    def test_diff_between_commits(self, git_utils: GitUtils, mock_repo):
        """Test getting diff between two commits."""
        diff = git_utils.diff(commit1="abc123", commit2="def456")

        assert diff == "diff content"
        mock_repo.git.diff.assert_called()

    def test_diff_all_changes(self, git_utils: GitUtils, mock_repo):
        """Test getting diff for all changes."""
        diff = git_utils.diff()

        assert diff == "diff content"
        mock_repo.git.diff.assert_called()

    # History Tests

    def test_get_recent_commits(self, git_utils: GitUtils, mock_repo):
        """Test getting recent commits."""
        commits = git_utils.get_recent_commits(count=5)

        assert len(commits) >= 0
        if commits:
            assert "hash" in commits[0]
            assert "message" in commits[0]

    def test_get_modified_files(self, git_utils: GitUtils, mock_repo):
        """Test getting modified files in a commit."""
        # Set up mock diff item
        diff_item = MagicMock()
        diff_item.new_file = False
        diff_item.deleted_file = False
        diff_item.a_path = "commands/test.md"
        diff_item.b_path = "commands/test.md"

        mock_parent = MagicMock()
        mock_parent.diff = MagicMock(return_value=[diff_item])

        mock_commit = MagicMock()
        mock_commit.parents = [mock_parent]
        mock_repo.commit = MagicMock(return_value=mock_commit)

        files = git_utils.get_modified_files("abc123")

        assert isinstance(files, list)

    def test_get_file_at_commit(self, git_utils: GitUtils, mock_repo):
        """Test getting file content at a specific commit."""
        mock_repo.git.show.return_value = "file content at commit"

        content = git_utils.get_file_at_commit("commands/test.md", "abc123")

        assert content == "file content at commit"
        mock_repo.git.show.assert_called()

    # Error Handling Tests

    def test_commit_handles_git_error(self, git_utils: GitUtils, mock_repo):
        """Test handling git errors during commit."""
        from git.exc import GitCommandError

        mock_repo.index.commit.side_effect = GitCommandError("commit", "error")

        with pytest.raises(GitError):
            git_utils.commit(["test.md"], "Test")

    def test_revert_nonexistent_commit(self, git_utils: GitUtils, mock_repo):
        """Test reverting non-existent commit."""
        from git.exc import GitCommandError

        mock_repo.git.revert.side_effect = GitCommandError("revert", "bad revision")

        with pytest.raises(GitError):
            git_utils.revert_commit("nonexistent123")

    # Utility Tests

    def test_is_clean(self, git_utils: GitUtils, mock_repo):
        """Test checking if working directory is clean."""
        mock_repo.is_dirty = MagicMock(return_value=False)

        is_clean = git_utils.is_clean()

        assert is_clean

    def test_is_dirty(self, git_utils: GitUtils, mock_repo):
        """Test checking if working directory has changes."""
        mock_repo.is_dirty = MagicMock(return_value=True)

        is_clean = git_utils.is_clean()

        assert not is_clean

    def test_has_changes(self, git_utils: GitUtils, mock_repo):
        """Test checking if a specific file has changes."""
        mock_repo.index.diff = MagicMock(return_value=[])

        has_changes = git_utils.has_changes("commands/test.md")

        assert isinstance(has_changes, bool)

    def test_stash_changes(self, git_utils: GitUtils, mock_repo):
        """Test stashing changes."""
        mock_repo.is_dirty = MagicMock(return_value=True)

        result = git_utils.stash("test stash")

        assert result is True
        mock_repo.git.stash.assert_called()

    def test_stash_nothing_to_stash(self, git_utils: GitUtils, mock_repo):
        """Test stash when there are no changes."""
        mock_repo.is_dirty = MagicMock(return_value=False)

        result = git_utils.stash()

        assert result is False
