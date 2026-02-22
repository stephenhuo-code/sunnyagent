"""Plugin package validator.

Validates uploaded plugin packages (ZIP files) for correct structure,
required files, and security considerations.
"""

import logging
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

logger = logging.getLogger(__name__)

# Maximum allowed file size for plugin packages (50MB)
MAX_PACKAGE_SIZE = 50 * 1024 * 1024

# Allowed file extensions in plugin packages
ALLOWED_EXTENSIONS = {
    ".md", ".txt", ".json", ".yaml", ".yml",  # Config/docs
    ".py",  # Python code (for future tool definitions)
    ".png", ".jpg", ".jpeg", ".svg",  # Icons
}

# Files that indicate valid plugin types
AGENT_MARKER = "AGENTS.md"
SKILL_MARKER = "SKILL.md"

# Invalid/dangerous file patterns
DANGEROUS_PATTERNS = [
    r"\.\.\/",  # Path traversal
    r"^\/",  # Absolute paths
    r"__pycache__",  # Python cache
    r"\.pyc$",  # Compiled Python
    r"\.exe$", r"\.dll$", r"\.so$",  # Binaries
    r"\.sh$", r"\.bat$", r"\.cmd$",  # Scripts
]


@dataclass
class ValidationResult:
    """Result of plugin package validation."""

    valid: bool
    plugin_name: str | None = None
    plugin_type: str | None = None  # "agent" or "skill"
    has_skills: bool = False
    skill_count: int = 0
    errors: list[str] | None = None
    warnings: list[str] | None = None


def validate_plugin_package(
    file: BinaryIO,
    filename: str,
    max_size: int = MAX_PACKAGE_SIZE,
) -> ValidationResult:
    """Validate a plugin package ZIP file.

    Checks:
    1. File is a valid ZIP archive
    2. Contains AGENTS.md or SKILL.md at root level
    3. No dangerous file patterns
    4. Size limits respected

    Args:
        file: File-like object containing the ZIP data
        filename: Original filename (for logging)
        max_size: Maximum allowed package size in bytes

    Returns:
        ValidationResult with validation status and details
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check file size
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to start

    if size > max_size:
        return ValidationResult(
            valid=False,
            errors=[f"Package too large: {size} bytes (max: {max_size})"],
        )

    # Check if valid ZIP
    if not zipfile.is_zipfile(file):
        return ValidationResult(
            valid=False,
            errors=["File is not a valid ZIP archive"],
        )

    file.seek(0)  # Reset after is_zipfile check

    try:
        with zipfile.ZipFile(file, "r") as zf:
            # Get all file names
            names = zf.namelist()

            if not names:
                return ValidationResult(
                    valid=False,
                    errors=["ZIP archive is empty"],
                )

            # Check for dangerous patterns
            for name in names:
                for pattern in DANGEROUS_PATTERNS:
                    if re.search(pattern, name):
                        errors.append(f"Dangerous file pattern detected: {name}")

            if errors:
                return ValidationResult(valid=False, errors=errors)

            # Determine plugin structure
            # Can be: root level files, or single directory containing files
            root_files = set()
            root_dirs = set()

            for name in names:
                parts = Path(name).parts
                if len(parts) == 1 and not name.endswith("/"):
                    root_files.add(name)
                elif len(parts) >= 1:
                    root_dirs.add(parts[0])

            # Check for markers at root level or in single root directory
            plugin_name = None
            plugin_type = None
            has_skills = False
            skill_count = 0

            # Case 1: Files at root level
            if AGENT_MARKER in root_files:
                plugin_type = "agent"
                plugin_name = Path(filename).stem
            elif SKILL_MARKER in root_files:
                plugin_type = "skill"
                plugin_name = Path(filename).stem

            # Case 2: Single directory at root containing the marker
            if plugin_type is None and len(root_dirs) == 1:
                single_dir = list(root_dirs)[0]
                dir_files = {
                    Path(n).name for n in names
                    if n.startswith(f"{single_dir}/") and len(Path(n).parts) == 2
                }

                if AGENT_MARKER in dir_files:
                    plugin_type = "agent"
                    plugin_name = single_dir
                elif SKILL_MARKER in dir_files:
                    plugin_type = "skill"
                    plugin_name = single_dir

            if plugin_type is None:
                return ValidationResult(
                    valid=False,
                    errors=[
                        f"Plugin package must contain {AGENT_MARKER} or {SKILL_MARKER} "
                        "at root level or in a single root directory"
                    ],
                )

            # Check for skills subdirectory (for agent type)
            if plugin_type == "agent":
                skills_dir_pattern = (
                    r"^skills/[^/]+/SKILL\.md$" if AGENT_MARKER in root_files
                    else rf"^{plugin_name}/skills/[^/]+/SKILL\.md$"
                )
                for name in names:
                    if re.match(skills_dir_pattern, name):
                        has_skills = True
                        skill_count += 1

            # Validate file extensions
            for name in names:
                if name.endswith("/"):
                    continue  # Skip directories

                ext = Path(name).suffix.lower()
                if ext and ext not in ALLOWED_EXTENSIONS:
                    warnings.append(f"Unusual file extension: {name}")

            logger.info(
                f"Plugin validation passed: name={plugin_name}, type={plugin_type}, "
                f"has_skills={has_skills}, skill_count={skill_count}"
            )

            return ValidationResult(
                valid=True,
                plugin_name=plugin_name,
                plugin_type=plugin_type,
                has_skills=has_skills,
                skill_count=skill_count,
                warnings=warnings if warnings else None,
            )

    except zipfile.BadZipFile as e:
        return ValidationResult(
            valid=False,
            errors=[f"Invalid ZIP file: {e}"],
        )
    except Exception as e:
        logger.exception(f"Plugin validation error: {e}")
        return ValidationResult(
            valid=False,
            errors=[f"Validation error: {e}"],
        )


def extract_plugin_package(
    file: BinaryIO,
    target_dir: Path,
    plugin_name: str,
) -> Path:
    """Extract a validated plugin package to target directory.

    Args:
        file: File-like object containing the validated ZIP data
        target_dir: Directory to extract to
        plugin_name: Name of the plugin (used for directory naming)

    Returns:
        Path to the extracted plugin directory

    Raises:
        ValueError: If extraction fails
    """
    file.seek(0)
    plugin_dir = target_dir / plugin_name

    # Remove existing directory if present
    if plugin_dir.exists():
        import shutil
        shutil.rmtree(plugin_dir)

    plugin_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(file, "r") as zf:
            names = zf.namelist()

            # Determine if files are in a subdirectory
            root_dirs = {Path(n).parts[0] for n in names if len(Path(n).parts) > 1}

            if len(root_dirs) == 1:
                # Files are in a single subdirectory - extract and flatten
                prefix = list(root_dirs)[0] + "/"
                for name in names:
                    if name.startswith(prefix) and not name.endswith("/"):
                        # Extract relative to the prefix
                        relative_path = name[len(prefix):]
                        target_path = plugin_dir / relative_path
                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        with zf.open(name) as src, open(target_path, "wb") as dst:
                            dst.write(src.read())
            else:
                # Files at root level - extract directly
                zf.extractall(plugin_dir)

        logger.info(f"Extracted plugin to: {plugin_dir}")
        return plugin_dir

    except Exception as e:
        # Clean up on failure
        if plugin_dir.exists():
            import shutil
            shutil.rmtree(plugin_dir)
        raise ValueError(f"Failed to extract plugin: {e}")
