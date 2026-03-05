"""Shared pytest fixtures for Meta-Agent tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_test_case() -> dict:
    """Create a sample test case."""
    return {
        "case_id": "test_001",
        "input": "/analyze quality.csv",
        "expected_behavior": "分析质量数据并计算CPK",
        "expected_skill": "data-profiler",
        "expected_contains": ["CPK", "合格率"],
        "context_files": ["quality.csv"],
    }


@pytest.fixture
def sample_dataset_jsonl(temp_dir: Path, sample_test_case: dict) -> Path:
    """Create a sample JSONL dataset file."""
    # Create test-resources structure
    datasets_dir = temp_dir / "test-resources" / "datasets"
    files_dir = temp_dir / "test-resources" / "files"
    datasets_dir.mkdir(parents=True)
    files_dir.mkdir(parents=True)

    # Create context file
    (files_dir / "quality.csv").write_text("data,value\n1,2\n")

    # Create dataset file
    dataset_file = datasets_dir / "test.jsonl"
    with open(dataset_file, "w") as f:
        f.write(json.dumps(sample_test_case) + "\n")
        f.write(
            json.dumps(
                {
                    "case_id": "test_002",
                    "input": "/another command",
                    "expected_behavior": "另一个测试",
                }
            )
            + "\n"
        )

    return dataset_file


@pytest.fixture
def mock_repo_root(temp_dir: Path) -> Path:
    """Create a mock repository root with plugin structure."""
    # Create packages directory
    packages_dir = temp_dir / "packages"
    packages_dir.mkdir()

    # Create a test plugin
    plugin_dir = packages_dir / "test-plugin"
    plugin_dir.mkdir()
    (plugin_dir / ".plugin").mkdir()
    (plugin_dir / "commands").mkdir()
    (plugin_dir / "skills").mkdir()

    # Create plugin.json
    plugin_json = {
        "name": "test-plugin",
        "version": "1.0.0",
        "description": "Test plugin for unit tests",
    }
    (plugin_dir / ".plugin" / "plugin.json").write_text(json.dumps(plugin_json))

    # Create a test command
    command_content = """---
description: Test command
skill: test-skill
---

# Test Command

This is a test command for unit testing.
"""
    (plugin_dir / "commands" / "test-command.md").write_text(command_content)

    # Create a test skill
    skill_dir = plugin_dir / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    skill_content = """---
name: test-skill
description: Test skill for unit tests
---

# Test Skill

This skill is for testing purposes.
"""
    (skill_dir / "SKILL.md").write_text(skill_content)

    return temp_dir
