"""
Script file manager for scheduled tasks.

Handles CRUD operations for script files stored in user directories.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# Base directory for scheduled task data
BASE_DIR = Path("data/scheduled_tasks")

# Max script file size (64KB)
MAX_SCRIPT_SIZE = 64 * 1024


class ScriptManager:
    """Manages script files for scheduled tasks."""

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the script manager.

        Args:
            base_dir: Base directory for scheduled task data.
                     Defaults to data/scheduled_tasks/
        """
        self.base_dir = base_dir or BASE_DIR

    def _get_user_dir(self, user_id: UUID) -> Path:
        """Get the directory for a user."""
        return self.base_dir / str(user_id)

    def _get_scripts_dir(self, user_id: UUID) -> Path:
        """Get the scripts directory for a user."""
        return self._get_user_dir(user_id) / "scripts"

    def _get_logs_dir(self, user_id: UUID) -> Path:
        """Get the logs directory for a user."""
        return self._get_user_dir(user_id) / "logs"

    def _get_task_logs_dir(self, user_id: UUID, task_id: UUID) -> Path:
        """Get the logs directory for a specific task."""
        return self._get_logs_dir(user_id) / str(task_id)

    def get_script_path(self, user_id: UUID, task_id: UUID) -> str:
        """
        Get the relative path for a script file.

        Args:
            user_id: The user ID
            task_id: The task ID

        Returns:
            Relative path to the script file
        """
        return str(Path(str(user_id)) / "scripts" / f"{task_id}.txt")

    def get_full_script_path(self, user_id: UUID, task_id: UUID) -> Path:
        """
        Get the full path for a script file.

        Args:
            user_id: The user ID
            task_id: The task ID

        Returns:
            Full path to the script file
        """
        return self._get_scripts_dir(user_id) / f"{task_id}.txt"

    def get_log_path(self, user_id: UUID, task_id: UUID, execution_id: UUID) -> str:
        """
        Get the relative path for a log file.

        Args:
            user_id: The user ID
            task_id: The task ID
            execution_id: The execution ID

        Returns:
            Relative path to the log file
        """
        return str(Path(str(user_id)) / "logs" / str(task_id) / f"{execution_id}.log")

    def get_full_log_path(self, user_id: UUID, task_id: UUID, execution_id: UUID) -> Path:
        """
        Get the full path for a log file.

        Args:
            user_id: The user ID
            task_id: The task ID
            execution_id: The execution ID

        Returns:
            Full path to the log file
        """
        return self._get_task_logs_dir(user_id, task_id) / f"{execution_id}.log"

    async def create_script(self, user_id: UUID, task_id: UUID, content: str) -> str:
        """
        Create a script file.

        Args:
            user_id: The user ID
            task_id: The task ID
            content: The script content

        Returns:
            Relative path to the created script file

        Raises:
            ValueError: If content exceeds max size
        """
        # Validate content size
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > MAX_SCRIPT_SIZE:
            raise ValueError(f"Script content exceeds maximum size of {MAX_SCRIPT_SIZE} bytes")

        # Ensure directory exists
        scripts_dir = self._get_scripts_dir(user_id)
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # Write script file
        script_path = self.get_full_script_path(user_id, task_id)
        script_path.write_text(content, encoding="utf-8")

        logger.info(f"Created script file: {script_path}")
        return self.get_script_path(user_id, task_id)

    async def read_script(self, user_id: UUID, task_id: UUID) -> Optional[str]:
        """
        Read a script file.

        Args:
            user_id: The user ID
            task_id: The task ID

        Returns:
            Script content or None if file doesn't exist
        """
        script_path = self.get_full_script_path(user_id, task_id)

        if not script_path.exists():
            logger.warning(f"Script file not found: {script_path}")
            return None

        return script_path.read_text(encoding="utf-8")

    async def update_script(self, user_id: UUID, task_id: UUID, content: str) -> str:
        """
        Update a script file.

        Args:
            user_id: The user ID
            task_id: The task ID
            content: The new script content

        Returns:
            Relative path to the updated script file

        Raises:
            ValueError: If content exceeds max size
            FileNotFoundError: If script file doesn't exist
        """
        script_path = self.get_full_script_path(user_id, task_id)

        if not script_path.exists():
            raise FileNotFoundError(f"Script file not found: {script_path}")

        # Validate content size
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > MAX_SCRIPT_SIZE:
            raise ValueError(f"Script content exceeds maximum size of {MAX_SCRIPT_SIZE} bytes")

        # Update script file
        script_path.write_text(content, encoding="utf-8")

        logger.info(f"Updated script file: {script_path}")
        return self.get_script_path(user_id, task_id)

    async def delete_script(self, user_id: UUID, task_id: UUID) -> bool:
        """
        Delete a script file.

        Args:
            user_id: The user ID
            task_id: The task ID

        Returns:
            True if deleted, False if file didn't exist
        """
        script_path = self.get_full_script_path(user_id, task_id)

        if not script_path.exists():
            return False

        script_path.unlink()
        logger.info(f"Deleted script file: {script_path}")
        return True

    async def write_log(
        self,
        user_id: UUID,
        task_id: UUID,
        execution_id: UUID,
        content: str,
        append: bool = False,
    ) -> str:
        """
        Write to a log file.

        Args:
            user_id: The user ID
            task_id: The task ID
            execution_id: The execution ID
            content: The log content
            append: Whether to append to existing file

        Returns:
            Relative path to the log file
        """
        # Ensure directory exists
        logs_dir = self._get_task_logs_dir(user_id, task_id)
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Write log file
        log_path = self.get_full_log_path(user_id, task_id, execution_id)
        mode = "a" if append else "w"
        with open(log_path, mode, encoding="utf-8") as f:
            f.write(content)

        return self.get_log_path(user_id, task_id, execution_id)

    async def read_log(
        self,
        user_id: UUID,
        task_id: UUID,
        execution_id: UUID,
    ) -> Optional[str]:
        """
        Read a log file.

        Args:
            user_id: The user ID
            task_id: The task ID
            execution_id: The execution ID

        Returns:
            Log content or None if file doesn't exist
        """
        log_path = self.get_full_log_path(user_id, task_id, execution_id)

        if not log_path.exists():
            return None

        return log_path.read_text(encoding="utf-8")

    async def delete_task_logs(self, user_id: UUID, task_id: UUID) -> bool:
        """
        Delete all logs for a task.

        Args:
            user_id: The user ID
            task_id: The task ID

        Returns:
            True if deleted, False if directory didn't exist
        """
        logs_dir = self._get_task_logs_dir(user_id, task_id)

        if not logs_dir.exists():
            return False

        shutil.rmtree(logs_dir)
        logger.info(f"Deleted task logs directory: {logs_dir}")
        return True

    async def delete_user_data(self, user_id: UUID) -> bool:
        """
        Delete all data for a user.

        Args:
            user_id: The user ID

        Returns:
            True if deleted, False if directory didn't exist
        """
        user_dir = self._get_user_dir(user_id)

        if not user_dir.exists():
            return False

        shutil.rmtree(user_dir)
        logger.info(f"Deleted user data directory: {user_dir}")
        return True

    # Alias for cleanup.py compatibility
    async def delete_user_directory(self, user_id: UUID) -> bool:
        """Alias for delete_user_data."""
        return await self.delete_user_data(user_id)

    async def cleanup_old_logs(self, days: int = 90) -> int:
        """
        Clean up log files older than specified days.

        Args:
            days: Number of days to retain logs

        Returns:
            Number of deleted log files
        """
        import time
        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(days=days)
        cutoff_timestamp = cutoff.timestamp()
        deleted_count = 0

        if not self.base_dir.exists():
            return 0

        # Iterate through all user directories
        for user_dir in self.base_dir.iterdir():
            if not user_dir.is_dir():
                continue

            logs_dir = user_dir / "logs"
            if not logs_dir.exists():
                continue

            # Iterate through task log directories
            for task_logs_dir in logs_dir.iterdir():
                if not task_logs_dir.is_dir():
                    continue

                # Delete old log files
                for log_file in task_logs_dir.iterdir():
                    if log_file.is_file() and log_file.stat().st_mtime < cutoff_timestamp:
                        log_file.unlink()
                        deleted_count += 1

                # Remove empty task log directories
                if not any(task_logs_dir.iterdir()):
                    task_logs_dir.rmdir()

        logger.info(f"Cleaned up {deleted_count} old log files")
        return deleted_count


# Global instance
script_manager = ScriptManager()
