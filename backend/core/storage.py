"""Centralized storage path configuration."""
import os
from pathlib import Path

# Project root directory
_PROJECT_ROOT = Path(__file__).parent.parent.parent


def get_project_files_dir() -> Path:
    """Get directory for project files (persistent storage)."""
    default = _PROJECT_ROOT / "data" / "project_files"
    return Path(os.getenv("PROJECT_FILES_DIR", str(default)))


def get_temp_files_dir() -> Path:
    """Get directory for temporary uploaded files."""
    default = _PROJECT_ROOT / "data" / "tmp"
    return Path(os.getenv("TEMP_FILES_DIR", str(default)))


# Ensure directories exist at import time
get_project_files_dir().mkdir(parents=True, exist_ok=True)
get_temp_files_dir().mkdir(parents=True, exist_ok=True)
