"""Git utilities for version control operations."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Literal

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

logger = logging.getLogger(__name__)


class GitError(Exception):
    """Git operation error."""

    pass


class GitUtils:
    """Git utility class for commit, revert, and diff operations."""

    def __init__(self, repo_root: str):
        """
        Initialize GitUtils.

        Args:
            repo_root: Path to the git repository root

        Raises:
            GitError: If repo_root is not a valid git repository
        """
        self.repo_root = Path(repo_root)
        try:
            self.repo = Repo(repo_root)
        except InvalidGitRepositoryError as e:
            raise GitError(f"Not a valid git repository: {repo_root}") from e

    def is_clean(self) -> bool:
        """Check if working directory is clean."""
        return not self.repo.is_dirty(untracked_files=True)

    def has_changes(self, file_path: str) -> bool:
        """Check if a specific file has uncommitted changes."""
        rel_path = self._relative_path(file_path)
        diff = self.repo.index.diff(None)  # Unstaged changes
        staged = self.repo.index.diff("HEAD")  # Staged changes

        for d in list(diff) + list(staged):
            if d.a_path == rel_path or d.b_path == rel_path:
                return True
        return False

    def commit(
        self,
        file_paths: list[str],
        message: str,
        prefix: str = "meta-agent:",
    ) -> str:
        """
        Commit specific files.

        Args:
            file_paths: List of file paths to commit
            message: Commit message
            prefix: Prefix for commit message

        Returns:
            Commit hash

        Raises:
            GitError: If commit fails
        """
        try:
            # Stage files
            for path in file_paths:
                rel_path = self._relative_path(path)
                self.repo.index.add([rel_path])

            # Create commit
            full_message = f"{prefix} {message}"
            commit = self.repo.index.commit(full_message)

            logger.info(f"Created commit {commit.hexsha[:7]}: {full_message}")
            return commit.hexsha

        except GitCommandError as e:
            raise GitError(f"Failed to commit: {e}") from e

    def revert_commit(self, commit_hash: str) -> str:
        """
        Revert a specific commit.

        Args:
            commit_hash: Hash of the commit to revert

        Returns:
            New commit hash (revert commit)

        Raises:
            GitError: If revert fails
        """
        try:
            # Run git revert
            self.repo.git.revert(commit_hash, "--no-edit")
            return self.repo.head.commit.hexsha

        except GitCommandError as e:
            raise GitError(f"Failed to revert commit {commit_hash}: {e}") from e

    def revert_file(self, file_path: str, commit_hash: str | None = None) -> None:
        """
        Revert a file to a specific commit or HEAD.

        Args:
            file_path: Path to the file
            commit_hash: Optional commit hash to revert to (defaults to HEAD)

        Raises:
            GitError: If revert fails
        """
        try:
            rel_path = self._relative_path(file_path)
            target = commit_hash or "HEAD"
            self.repo.git.checkout(target, "--", rel_path)
            logger.info(f"Reverted {rel_path} to {target}")

        except GitCommandError as e:
            raise GitError(f"Failed to revert file {file_path}: {e}") from e

    def get_file_at_commit(self, file_path: str, commit_hash: str) -> str:
        """
        Get file content at a specific commit.

        Args:
            file_path: Path to the file
            commit_hash: Commit hash

        Returns:
            File content at that commit

        Raises:
            GitError: If operation fails
        """
        try:
            rel_path = self._relative_path(file_path)
            return self.repo.git.show(f"{commit_hash}:{rel_path}")
        except GitCommandError as e:
            raise GitError(
                f"Failed to get {file_path} at commit {commit_hash}: {e}"
            ) from e

    def diff(
        self,
        file_path: str | None = None,
        commit1: str = "HEAD~1",
        commit2: str = "HEAD",
    ) -> str:
        """
        Get diff between commits.

        Args:
            file_path: Optional specific file to diff
            commit1: First commit (older)
            commit2: Second commit (newer)

        Returns:
            Diff output as string
        """
        try:
            if file_path:
                rel_path = self._relative_path(file_path)
                return self.repo.git.diff(commit1, commit2, "--", rel_path)
            return self.repo.git.diff(commit1, commit2)
        except GitCommandError as e:
            raise GitError(f"Failed to get diff: {e}") from e

    def get_recent_commits(self, count: int = 10) -> list[dict[str, str]]:
        """
        Get recent commits.

        Args:
            count: Number of commits to retrieve

        Returns:
            List of commit info dicts
        """
        commits = []
        for commit in self.repo.iter_commits(max_count=count):
            commits.append(
                {
                    "hash": commit.hexsha,
                    "short_hash": commit.hexsha[:7],
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "date": datetime.fromtimestamp(commit.committed_date).isoformat(),
                }
            )
        return commits

    def get_modified_files(
        self,
        commit_hash: str | None = None,
    ) -> list[dict[str, str]]:
        """
        Get files modified in a commit.

        Args:
            commit_hash: Commit hash (defaults to HEAD)

        Returns:
            List of modified file info
        """
        target = commit_hash or "HEAD"
        try:
            commit = self.repo.commit(target)
            parent = commit.parents[0] if commit.parents else None

            files = []
            if parent:
                for diff_item in parent.diff(commit):
                    change_type: Literal["create", "update", "delete"]
                    if diff_item.new_file:
                        change_type = "create"
                    elif diff_item.deleted_file:
                        change_type = "delete"
                    else:
                        change_type = "update"

                    files.append(
                        {
                            "path": diff_item.a_path or diff_item.b_path,
                            "change_type": change_type,
                        }
                    )
            return files

        except Exception as e:
            raise GitError(f"Failed to get modified files: {e}") from e

    def stash(self, message: str | None = None) -> bool:
        """
        Stash current changes.

        Args:
            message: Optional stash message

        Returns:
            True if changes were stashed, False if nothing to stash
        """
        if self.is_clean():
            return False

        try:
            if message:
                self.repo.git.stash("push", "-m", message)
            else:
                self.repo.git.stash("push")
            return True
        except GitCommandError as e:
            raise GitError(f"Failed to stash: {e}") from e

    def stash_pop(self) -> None:
        """Pop the most recent stash."""
        try:
            self.repo.git.stash("pop")
        except GitCommandError as e:
            raise GitError(f"Failed to pop stash: {e}") from e

    def _relative_path(self, file_path: str) -> str:
        """Convert to relative path from repo root."""
        path = Path(file_path)
        if path.is_absolute():
            try:
                return str(path.relative_to(self.repo_root))
            except ValueError:
                # Path is not relative to repo root
                return file_path
        return file_path
