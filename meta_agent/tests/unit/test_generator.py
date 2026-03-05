"""Unit tests for GeneratorAgent."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from meta_agent.agents.generator import GeneratorAgent
from meta_agent.agents.base import AgentContext
from meta_agent.agents.analyzer import AnalysisResult, ImprovementSuggestion
from meta_agent.models.plugin import Command, CommandFrontmatter, Skill, SkillFrontmatter
from meta_agent.models.evaluation import FailureCategory


class TestGeneratorAgent:
    """Tests for GeneratorAgent."""

    @pytest.fixture
    def mock_file_service(self):
        """Create a mock FileService."""
        service = MagicMock()
        service.list_commands = MagicMock(return_value=["quality-data"])
        service.list_skills = MagicMock(return_value=["data-profiler"])
        service.read_command = MagicMock(
            return_value=Command(
                name="quality-data",
                plugin_name="test-plugin",
                frontmatter=CommandFrontmatter(
                    description="Analyze quality data",
                ),
                content="# Quality Data\n\nAnalyze quality data.",
                file_path="packages/test-plugin/commands/quality-data.md",
            )
        )
        service.write_command = MagicMock(
            return_value="packages/test-plugin/commands/quality-data.md"
        )
        service.read_skill = MagicMock(
            return_value=Skill(
                name="data-profiler",
                plugin_name="test-plugin",
                frontmatter=SkillFrontmatter(
                    name="data-profiler",
                    description="Profile and analyze data",
                ),
                content="# Data Profiler\n\nAnalyze and profile data.",
                file_path="packages/test-plugin/skills/data-profiler/SKILL.md",
            )
        )
        service.write_skill = MagicMock(
            return_value="packages/test-plugin/skills/data-profiler/SKILL.md"
        )
        service.backup_file = MagicMock(return_value="backup-path")
        return service

    @pytest.fixture
    def mock_git_utils(self):
        """Create a mock GitUtils."""
        git = MagicMock()
        git.commit = MagicMock(return_value="abc123")
        git.revert_commit = MagicMock()
        git.diff = MagicMock(return_value="diff content")
        return git

    @pytest.fixture
    def agent(self, mock_file_service, mock_git_utils) -> GeneratorAgent:
        """Create a GeneratorAgent instance."""
        return GeneratorAgent(
            file_service=mock_file_service,
            git_utils=mock_git_utils,
            api_key="test-key",
        )

    @pytest.fixture
    def sample_suggestion(self) -> ImprovementSuggestion:
        """Create a sample suggestion."""
        return ImprovementSuggestion(
            category=FailureCategory.SKILL_NOT_TRIGGERED,
            priority=1,
            description="Add trigger phrases to improve intent matching",
            affected_cases=["test_001", "test_002"],
        )

    @pytest.fixture
    def sample_analysis_result(self, sample_suggestion) -> AnalysisResult:
        """Create a sample analysis result."""
        return AnalysisResult(
            total_failures=2,
            failures_by_category={"skill_not_triggered": 2},
            suggestions=[sample_suggestion],
            summary="Needs trigger phrase improvement",
        )

    # Command Generation Tests

    @pytest.mark.asyncio
    async def test_generate_command_modification(
        self, agent: GeneratorAgent, sample_analysis_result
    ):
        """Test generating a command modification."""
        context = AgentContext(
            plugin_name="test-plugin",
        )
        context.analysis_result = sample_analysis_result

        # Mock LLM response
        llm_response = """TYPE: MODIFY_COMMAND
TARGET: quality-data
DESCRIPTION: Add trigger phrases for better intent matching
CONTENT: # Quality Data\n\nUpdated content."""

        with patch.object(agent, "call_llm", return_value=llm_response):
            result = await agent.run(context)

        assert result.success
        assert result.data is not None
        assert hasattr(result.data, "changes")

    @pytest.mark.asyncio
    async def test_run_with_no_suggestions(self, agent: GeneratorAgent):
        """Test running with no suggestions."""
        context = AgentContext(
            plugin_name="test-plugin",
        )
        context.analysis_result = AnalysisResult(
            total_failures=0,
            suggestions=[],
        )

        result = await agent.run(context)

        assert result.success
        assert "No suggestions" in result.message or "No changes" in result.data.summary

    @pytest.mark.asyncio
    async def test_run_without_analysis_result(self, agent: GeneratorAgent):
        """Test running without analysis result."""
        context = AgentContext(plugin_name="test-plugin")

        result = await agent.run(context)

        assert not result.success
        assert "No analysis result" in result.error

    # Modification Parsing Tests

    def test_parse_modification_response_valid(self, agent: GeneratorAgent):
        """Test parsing a valid modification response."""
        response = """TYPE: MODIFY_COMMAND
TARGET: quality-data
DESCRIPTION: Add trigger phrases
CONTENT: # New content here"""

        result = agent._parse_modification_response(response)

        assert result is not None
        assert result["type"] == "MODIFY_COMMAND"
        assert result["target"] == "quality-data"
        assert "CONTENT" not in result["content"]  # CONTENT: prefix stripped

    def test_parse_modification_response_invalid(self, agent: GeneratorAgent):
        """Test parsing an invalid modification response."""
        response = "This is not a valid response format"

        result = agent._parse_modification_response(response)

        assert result is None

    # Rollback Tests

    @pytest.mark.asyncio
    async def test_rollback_change(self, agent: GeneratorAgent, mock_git_utils):
        """Test rolling back a change."""
        from meta_agent.agents.generator import FileChange

        change = FileChange(
            file_path="packages/test-plugin/commands/test.md",
            change_type="update",
            description="Test change",
            git_commit_hash="abc123",
        )

        success = await agent.rollback_change(change)

        assert success
        mock_git_utils.revert_commit.assert_called_once_with("abc123")

    @pytest.mark.asyncio
    async def test_rollback_change_no_commit_hash(self, agent: GeneratorAgent):
        """Test rollback fails without commit hash."""
        from meta_agent.agents.generator import FileChange

        change = FileChange(
            file_path="packages/test-plugin/commands/test.md",
            change_type="update",
            description="Test change",
            git_commit_hash="",  # No commit hash
        )

        success = await agent.rollback_change(change)

        assert not success
