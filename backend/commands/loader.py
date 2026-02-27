"""Loader for command files from packages/*/commands/ directories."""

import logging
import re
from pathlib import Path

import yaml

from backend.commands.registry import CommandEntry, register_command

logger = logging.getLogger(__name__)


def parse_command_metadata(cmd_path: Path) -> tuple[str | None, str, str]:
    """Parse YAML frontmatter from a command .md file.

    Returns (name, description, argument_hint) where:
    - name: Command name derived from filename (without extension)
    - description: From YAML frontmatter 'description' field
    - argument_hint: From YAML frontmatter 'argument-hint' field

    Returns (None, "", "") if parsing fails.

    YAML frontmatter format:
        ---
        description: Command description
        argument-hint: "<question>"
        ---
    """
    try:
        content = cmd_path.read_text()
    except Exception as e:
        logger.warning(f"Failed to read {cmd_path}: {e}")
        return None, "", ""

    # Extract YAML frontmatter between --- markers
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        logger.warning(f"No YAML frontmatter in {cmd_path}")
        return None, "", ""

    try:
        metadata = yaml.safe_load(match.group(1))
        if not isinstance(metadata, dict):
            logger.warning(f"Invalid YAML metadata in {cmd_path}")
            return None, "", ""

        # Use filename (without extension) as command name
        name = cmd_path.stem
        description = metadata.get("description", "")
        argument_hint = metadata.get("argument-hint", "")

        # Handle case where YAML parses [xxx] as a list instead of string
        if isinstance(argument_hint, list):
            argument_hint = ", ".join(str(item) for item in argument_hint)

        return name, description, argument_hint

    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML in {cmd_path}: {e}")
        return None, "", ""


def load_commands_from_directory(commands_dir: Path, plugin_name: str) -> int:
    """Load all command files from a directory.

    Args:
        commands_dir: Directory containing command .md files
        plugin_name: Plugin name to associate with commands (e.g., "package:data")

    Returns:
        Number of commands loaded
    """
    if not commands_dir.exists():
        return 0

    count = 0
    for cmd_file in sorted(commands_dir.glob("*.md")):
        if not cmd_file.is_file():
            continue

        name, description, argument_hint = parse_command_metadata(cmd_file)
        if name:
            entry = CommandEntry(
                name=name,
                description=description,
                argument_hint=argument_hint,
                path=cmd_file,
                plugin_name=plugin_name,
            )
            register_command(entry)
            logger.info(f"Registered command: /{name} ({plugin_name})")
            count += 1

    return count
