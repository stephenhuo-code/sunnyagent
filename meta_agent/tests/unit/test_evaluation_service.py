"""Unit tests for EvaluationService."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from meta_agent.services.evaluation_service import EvaluationService
from meta_agent.models.dataset import TestCase, TestDataset
from meta_agent.models.evaluation import CaseScore, ChatResponse


class TestEvaluationService:
    """Tests for EvaluationService."""

    @pytest.fixture
    def mock_sunnyagent_client(self):
        """Create a mock SunnyAgentClient."""
        client = MagicMock()
        client.login = AsyncMock()
        client.logout = AsyncMock()
        client.get_project = AsyncMock(return_value=MagicMock(id="proj-123"))
        client.create_project = AsyncMock(return_value=MagicMock(id="proj-123"))
        client.delete_project = AsyncMock()
        client.create_conversation = AsyncMock(
            return_value=MagicMock(id="conv-123", thread_id="thread-123")
        )
        client.send_message_and_wait = AsyncMock(
            return_value=MagicMock(
                content="分析结果显示 CPK 值为 1.33，合格率达到 95%",
                tool_calls=[],
                agent_used=None,
                skill_used="data-profiler",
                langfuse_trace_id="trace-123",
            )
        )
        return client

    @pytest.fixture
    def mock_langfuse_client(self):
        """Create a mock LangfuseClient."""
        client = MagicMock()
        client.get_trace_detail = AsyncMock(
            return_value=MagicMock(
                id="trace-123",
                spans=[],
                generations=[],
            )
        )
        client.add_score = AsyncMock()
        client.add_scores_batch = AsyncMock()
        return client

    @pytest.fixture
    def mock_score_calculator(self):
        """Create a mock ScoreCalculator."""
        calculator = MagicMock()
        calculator.calculate_case_score = MagicMock(
            return_value=CaseScore(
                correctness=1.0,
                skill_trigger=1.0,
                response_quality=0.9,
                file_context_usage=1.0,
                overall=0.95,
            )
        )
        calculator.aggregate_scores = MagicMock(
            return_value={
                "correctness": 1.0,
                "skill_trigger": 1.0,
                "response_quality": 0.9,
                "file_context_usage": 1.0,
                "overall": 0.95,
            }
        )
        calculator.extract_file_operations = MagicMock(return_value=["quality.csv"])
        return calculator

    @pytest.fixture
    def service(
        self,
        mock_sunnyagent_client,
        mock_langfuse_client,
        mock_score_calculator,
    ) -> EvaluationService:
        """Create an EvaluationService instance."""
        return EvaluationService(
            sunnyagent_client=mock_sunnyagent_client,
            langfuse_client=mock_langfuse_client,
            score_calculator=mock_score_calculator,
        )

    @pytest.fixture
    def sample_test_case(self) -> TestCase:
        """Create a sample test case."""
        return TestCase(
            case_id="test_001",
            input="/analyze quality.csv",
            expected_behavior="分析质量数据并计算CPK",
            expected_skill="data-profiler",
            expected_output_contains=["CPK", "合格率"],
            context_files=["quality.csv"],
        )

    @pytest.fixture
    def sample_dataset(self, sample_test_case: TestCase) -> TestDataset:
        """Create a sample dataset."""
        return TestDataset(
            name="test-dataset",
            plugin_name="test-plugin",
            cases=[sample_test_case],
        )

    @pytest.mark.asyncio
    async def test_run_single_case_success(
        self, service: EvaluationService, sample_test_case: TestCase
    ):
        """Test running a single test case successfully."""
        result = await service.run_single_case(
            case=sample_test_case,
            project_id="proj-123",
            file_id_map={"quality.csv": "file-123"},
        )

        assert result.case_id == "test_001"
        assert result.passed is True
        assert result.scores is not None
        assert result.scores.overall == 0.95

    @pytest.mark.asyncio
    async def test_run_single_case_failure(
        self, service: EvaluationService, sample_test_case: TestCase, mock_sunnyagent_client
    ):
        """Test handling failure in single case execution."""
        from meta_agent.services.sunnyagent_client import SunnyAgentError

        # Make the send_message_and_wait fail
        mock_sunnyagent_client.send_message_and_wait = AsyncMock(
            side_effect=SunnyAgentError("API Error")
        )

        result = await service.run_single_case(
            case=sample_test_case,
            project_id="proj-123",
            file_id_map={},
        )

        assert result.case_id == "test_001"
        assert result.passed is False
        assert result.error is not None
        assert "API Error" in result.error

    @pytest.mark.asyncio
    async def test_run_evaluation_success(
        self, service: EvaluationService, sample_dataset: TestDataset
    ):
        """Test running full evaluation on a dataset."""
        result = await service.run_evaluation(
            dataset=sample_dataset,
            project_name="test-project",
        )

        assert result.dataset_name == "test-dataset"
        assert result.total_cases == 1
        assert result.passed_cases == 1
        assert result.pass_rate == 1.0

    @pytest.mark.asyncio
    async def test_run_evaluation_with_failures(
        self, service: EvaluationService, sample_dataset: TestDataset, mock_sunnyagent_client
    ):
        """Test evaluation with some failing cases."""
        from meta_agent.services.sunnyagent_client import SunnyAgentError

        # Add another case that will fail
        failing_case = TestCase(
            case_id="test_002",
            input="/failing command",
            expected_behavior="This will fail",
        )
        sample_dataset.cases.append(failing_case)

        # Make second call fail
        call_count = 0

        async def mock_send(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise SunnyAgentError("Simulated failure")
            return MagicMock(
                content="分析结果显示 CPK 值为 1.33，合格率达到 95%",
                tool_calls=[],
                agent_used=None,
                skill_used="data-profiler",
                langfuse_trace_id="trace-123",
            )

        mock_sunnyagent_client.send_message_and_wait = mock_send

        result = await service.run_evaluation(
            dataset=sample_dataset,
            project_name="test-project",
        )

        assert result.total_cases == 2
        # First passed, second failed
        assert result.passed_cases == 1
        assert result.failed_cases == 1

    @pytest.mark.asyncio
    async def test_calculate_case_score_uses_calculator(
        self, service: EvaluationService, sample_test_case: TestCase, mock_score_calculator
    ):
        """Test that calculate_case_score uses the score calculator."""
        response = ChatResponse(
            content="Test response with CPK",
            skill_used="data-profiler",
            langfuse_trace_id="trace-123",
        )

        score = await service.calculate_case_score(
            case=sample_test_case,
            response=response,
        )

        # Verify calculator was called
        mock_score_calculator.calculate_case_score.assert_called_once()
        assert score.overall == 0.95

    @pytest.mark.asyncio
    async def test_setup_test_environment(
        self, service: EvaluationService, mock_sunnyagent_client
    ):
        """Test setting up test environment."""
        project_id, file_map = await service.setup_test_environment(
            project_name="test-project",
            files=[],
        )

        assert project_id == "proj-123"
        mock_sunnyagent_client.login.assert_called_once()
        mock_sunnyagent_client.get_project.assert_called_once_with("test-project")

    @pytest.mark.asyncio
    async def test_cleanup_test_environment(
        self, service: EvaluationService, mock_sunnyagent_client
    ):
        """Test cleaning up test environment."""
        await service.cleanup_test_environment(
            project_id="proj-123",
            delete_project=True,
        )

        mock_sunnyagent_client.delete_project.assert_called_once_with("proj-123")
        mock_sunnyagent_client.logout.assert_called_once()
