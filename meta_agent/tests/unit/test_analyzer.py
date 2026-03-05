"""Unit tests for AnalyzerAgent."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from meta_agent.agents.analyzer import AnalyzerAgent
from meta_agent.agents.base import AgentContext
from meta_agent.models.evaluation import (
    EvaluationResult,
    FailedCase,
    FailureCategory,
)


class TestAnalyzerAgent:
    """Tests for AnalyzerAgent."""

    @pytest.fixture
    def mock_anthropic_response(self):
        """Create a mock Anthropic response."""
        mock_content = MagicMock()
        mock_content.text = """Based on the analysis, here are the findings:

1. **Pattern**: skill_not_triggered failures
   - Frequency: 3 cases
   - Root cause: Missing intent keywords
   - Suggestion: Add trigger phrases to command description

2. **Pattern**: output_incomplete failures
   - Frequency: 2 cases
   - Root cause: Skill doesn't include all required data points
   - Suggestion: Update skill instructions to include all metrics
"""
        mock_message = MagicMock()
        mock_message.content = [mock_content]
        return mock_message

    @pytest.fixture
    def agent(self) -> AnalyzerAgent:
        """Create an AnalyzerAgent instance."""
        return AnalyzerAgent(api_key="test-key")

    @pytest.fixture
    def sample_failed_cases(self) -> list[FailedCase]:
        """Create sample failed cases."""
        return [
            FailedCase(
                case_id="test_001",
                actual_output="Some response without expected data",
                actual_skill=None,
                scores={"correctness": 0.3, "skill_trigger": 0.0},
                failure_category=FailureCategory.SKILL_NOT_TRIGGERED,
                failure_reason="Expected skill 'data-profiler' was not triggered",
                file_related=True,
                langfuse_trace_id="trace-001",
            ),
            FailedCase(
                case_id="test_002",
                actual_output="Partial analysis without CPK",
                actual_skill="data-profiler",
                scores={"correctness": 0.5, "skill_trigger": 1.0},
                failure_category=FailureCategory.OUTPUT_INCOMPLETE,
                failure_reason="Missing keywords: ['CPK']",
                file_related=False,
                langfuse_trace_id="trace-002",
            ),
            FailedCase(
                case_id="test_003",
                actual_output="Wrong skill response",
                actual_skill="report-generator",
                scores={"correctness": 0.0, "skill_trigger": 0.0},
                failure_category=FailureCategory.WRONG_SKILL_TRIGGERED,
                failure_reason="Expected 'data-profiler', got 'report-generator'",
                file_related=False,
                langfuse_trace_id="trace-003",
            ),
        ]

    @pytest.fixture
    def sample_evaluation_result(self, sample_failed_cases) -> EvaluationResult:
        """Create a sample evaluation result."""
        return EvaluationResult(
            evaluation_id="eval-123",
            dataset_name="test-dataset",
            dataset_version="v1",
            iteration=1,
            total_cases=5,
            passed_cases=2,
            failed_cases=3,
            failed_case_details=sample_failed_cases,
            overall_score=0.4,
        )

    # Failure Categorization Tests

    def test_categorize_failures_by_type(self, agent: AnalyzerAgent, sample_failed_cases):
        """Test categorizing failures by type."""
        categorized = agent._categorize_failures(sample_failed_cases)

        assert FailureCategory.SKILL_NOT_TRIGGERED in categorized
        assert FailureCategory.OUTPUT_INCOMPLETE in categorized
        assert FailureCategory.WRONG_SKILL_TRIGGERED in categorized

        assert categorized[FailureCategory.SKILL_NOT_TRIGGERED] == 1
        assert categorized[FailureCategory.OUTPUT_INCOMPLETE] == 1
        assert categorized[FailureCategory.WRONG_SKILL_TRIGGERED] == 1

    def test_categorize_failures_empty_list(self, agent: AnalyzerAgent):
        """Test categorizing empty failure list."""
        categorized = agent._categorize_failures([])
        assert categorized == {}

    def test_identify_file_related_failures(self, agent: AnalyzerAgent, sample_failed_cases):
        """Test identifying file-related failures."""
        file_related = [c for c in sample_failed_cases if c.file_related]

        assert len(file_related) == 1
        assert file_related[0].case_id == "test_001"

    # Suggestion Generation Tests

    @pytest.mark.asyncio
    async def test_generate_suggestions_returns_result(
        self, agent: AnalyzerAgent, sample_evaluation_result, mock_anthropic_response
    ):
        """Test that generate_suggestions returns a result with suggestions."""
        context = AgentContext(
            plugin_name="test-plugin",
        )
        context.evaluation_result = sample_evaluation_result

        # Mock the LLM call
        with patch.object(agent, "call_llm", return_value="Add trigger phrases to improve matching"):
            result = await agent.run(context)

        assert result.success
        assert result.data is not None
        assert hasattr(result.data, "suggestions")

    @pytest.mark.asyncio
    async def test_analyze_categorizes_by_frequency(
        self, agent: AnalyzerAgent, sample_failed_cases
    ):
        """Test that analysis categorizes failures by frequency."""
        # Add more cases of same type
        additional_cases = [
            FailedCase(
                case_id=f"test_00{i}",
                actual_output="No skill triggered",
                actual_skill=None,
                scores={"correctness": 0.0, "skill_trigger": 0.0},
                failure_category=FailureCategory.SKILL_NOT_TRIGGERED,
                failure_reason="Skill not triggered",
                file_related=False,
            )
            for i in range(4, 7)
        ]

        all_cases = sample_failed_cases + additional_cases
        categorized = agent._categorize_failures(all_cases)

        # SKILL_NOT_TRIGGERED should have most cases (4 total)
        assert categorized.get(FailureCategory.SKILL_NOT_TRIGGERED, 0) == 4

    def test_calculate_priority(self, agent: AnalyzerAgent):
        """Test calculating priority for different categories."""
        # SKILL_NOT_TRIGGERED with high frequency should have high priority
        priority_skill = agent._calculate_priority(
            FailureCategory.SKILL_NOT_TRIGGERED, count=10
        )
        priority_timeout = agent._calculate_priority(
            FailureCategory.TIMEOUT, count=1
        )

        # SKILL_NOT_TRIGGERED with high count should have higher priority (lower number)
        assert priority_skill < priority_timeout

    def test_estimate_impact(self, agent: AnalyzerAgent):
        """Test estimating impact of fixing a category."""
        # Fix category with more failures = higher impact
        impact_high = agent._estimate_impact(
            FailureCategory.SKILL_NOT_TRIGGERED,
            category_count=5,
            total_failures=10,
        )
        impact_low = agent._estimate_impact(
            FailureCategory.TIMEOUT,
            category_count=1,
            total_failures=10,
        )

        assert impact_high > impact_low

    @pytest.mark.asyncio
    async def test_run_with_no_failures(self, agent: AnalyzerAgent):
        """Test running analyzer with no failures."""
        context = AgentContext(
            plugin_name="test-plugin",
        )

        result = EvaluationResult(
            evaluation_id="eval-123",
            dataset_name="test-dataset",
            dataset_version="v1",
            iteration=1,
            total_cases=5,
            passed_cases=5,
            failed_cases=0,
            failed_case_details=[],
            overall_score=1.0,
        )
        context.evaluation_result = result

        with patch.object(agent, "call_llm", return_value="No issues found"):
            agent_result = await agent.run(context)

        assert agent_result.success
        # No suggestions needed when all pass
        assert agent_result.data.total_failures == 0
