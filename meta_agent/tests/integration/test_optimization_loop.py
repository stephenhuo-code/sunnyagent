"""Integration tests for the full optimization loop.

These tests verify the complete optimization workflow:
Environment Setup -> Evaluation -> Analysis -> Generation -> Review -> Re-evaluation

Note: These tests use mocks for external services (SunnyAgent, Langfuse)
but test the real integration between internal components.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from meta_agent.agents.orchestrator import OrchestratorAgent
from meta_agent.agents.base import AgentContext, AgentResult
from meta_agent.models.optimization import OptimizationConfig, OptimizationState
from meta_agent.models.evaluation import EvaluationResult, FailureCategory
from meta_agent.models.dataset import TestDataset, TestCase
from meta_agent.services.file_service import FileService
from meta_agent.services.dataset_service import DatasetService
from meta_agent.utils.git_utils import GitUtils


class TestOptimizationLoop:
    """Integration tests for the full optimization loop."""

    @pytest.fixture
    def tmp_workspace(self, tmp_path) -> Path:
        """Create a temporary workspace with required directories."""
        # Create directory structure
        (tmp_path / "packages" / "test-plugin" / "commands").mkdir(parents=True)
        (tmp_path / "packages" / "test-plugin" / "skills" / "data-profiler").mkdir(parents=True)
        (tmp_path / ".checkpoints").mkdir()
        (tmp_path / "test-resources" / "datasets").mkdir(parents=True)
        (tmp_path / "test-resources" / "files").mkdir(parents=True)
        (tmp_path / "results").mkdir()

        # Create a sample command file
        command_content = """---
description: Analyze data quality
---

# Data Analysis

Analyze data quality metrics.
"""
        (tmp_path / "packages" / "test-plugin" / "commands" / "analyze.md").write_text(command_content)

        # Create a sample skill file
        skill_content = """---
name: data-profiler
description: Profile and analyze data
---

# Data Profiler

Profile data and generate statistics.
"""
        (tmp_path / "packages" / "test-plugin" / "skills" / "data-profiler" / "SKILL.md").write_text(skill_content)

        return tmp_path

    @pytest.fixture
    def sample_dataset(self, tmp_workspace) -> TestDataset:
        """Create a sample test dataset."""
        cases = [
            TestCase(
                case_id="test_001",
                input="/analyze 分析数据质量",
                expected_skill="data-profiler",
                expected_behavior="Should analyze data quality and return metrics",
                expected_output_contains=["质量", "分析"],
            ),
            TestCase(
                case_id="test_002",
                input="/analyze 计算CPK值",
                expected_skill="data-profiler",
                expected_behavior="Should calculate CPK value",
                expected_output_contains=["CPK"],
            ),
            TestCase(
                case_id="test_003",
                input="/analyze 生成报告",
                expected_skill="data-profiler",
                expected_behavior="Should generate analysis report",
                expected_output_contains=["报告"],
            ),
        ]

        dataset = TestDataset(
            name="test-dataset",
            version="v1",
            plugin_name="test-plugin",
            cases=cases,
            source_file=str(tmp_workspace / "test-resources" / "datasets" / "test.jsonl"),
        )

        # Save dataset file
        dataset_path = tmp_workspace / "test-resources" / "datasets" / "test.jsonl"
        with open(dataset_path, "w") as f:
            for case in cases:
                f.write(json.dumps(case.model_dump(), ensure_ascii=False) + "\n")

        return dataset

    @pytest.fixture
    def config(self, tmp_workspace, sample_dataset) -> OptimizationConfig:
        """Create optimization configuration."""
        return OptimizationConfig(
            target_plugin="test-plugin",
            dataset_path=str(tmp_workspace / "test-resources" / "datasets" / "test.jsonl"),
            target_score=0.85,
            max_iterations=3,
            patience=2,
            regression_threshold=0.05,
            test_project_name="integration-test-project",
        )

    @pytest.fixture
    def mock_sunnyagent_client(self):
        """Create a mock SunnyAgent client."""
        client = MagicMock()
        client.login = AsyncMock()
        client.logout = AsyncMock()
        client.create_project = AsyncMock(return_value=MagicMock(id="proj-123", name="test-project"))
        client.get_project = AsyncMock(return_value=None)
        client.delete_project = AsyncMock()
        client.upload_file = AsyncMock(return_value=MagicMock(id="file-123"))
        client.create_conversation = AsyncMock(return_value=MagicMock(id="conv-123", thread_id="thread-123"))
        client.send_message_and_wait = AsyncMock(
            return_value=MagicMock(
                content="分析完成，质量指标如下...",
                skill_used="data-profiler",
                langfuse_trace_id="trace-123",
            )
        )
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_langfuse_client(self):
        """Create a mock Langfuse client."""
        client = MagicMock()
        client.create_dataset = MagicMock(return_value="dataset-123")
        client.create_dataset_item = MagicMock()
        client.get_trace = MagicMock(return_value={"id": "trace-123", "output": "分析结果"})
        client.add_score = MagicMock()
        return client

    @pytest.fixture
    def file_service(self, tmp_workspace) -> FileService:
        """Create a real FileService."""
        return FileService(repo_root=str(tmp_workspace))

    @pytest.fixture
    def mock_git_utils(self):
        """Create a mock GitUtils."""
        git = MagicMock(spec=GitUtils)
        git.commit = MagicMock(return_value="abc123def456")
        git.revert_commit = MagicMock()
        git.is_clean = MagicMock(return_value=True)
        return git

    @pytest.fixture
    def dataset_service(self, tmp_workspace) -> DatasetService:
        """Create a real DatasetService."""
        return DatasetService(base_dir=str(tmp_workspace))

    # Integration Tests

    @pytest.mark.asyncio
    async def test_full_optimization_loop_reaches_target(
        self,
        tmp_workspace,
        config,
        sample_dataset,
        mock_sunnyagent_client,
        mock_langfuse_client,
        file_service,
        mock_git_utils,
        dataset_service,
    ):
        """Test that optimization loop runs and reaches target score."""
        # Create mock agents
        environment_agent = MagicMock()
        environment_agent.run = AsyncMock(return_value=AgentResult.ok("Environment ready"))
        environment_agent.cleanup = AsyncMock()

        evaluator_agent = MagicMock()
        analyzer_agent = MagicMock()
        generator_agent = MagicMock()
        generator_agent.rollback_change = AsyncMock(return_value=True)
        reviewer_agent = MagicMock()

        # Mock evaluation results that improve over iterations
        iteration_count = [0]

        async def mock_evaluator_run(context):
            iteration_count[0] += 1
            score = 0.60 + iteration_count[0] * 0.15  # 0.75, 0.90, ...

            eval_result = EvaluationResult(
                evaluation_id=f"eval-{iteration_count[0]}",
                dataset_name="test-dataset",
                dataset_version="v1",
                iteration=iteration_count[0],
                total_cases=3,
                passed_cases=int(3 * score),
                failed_cases=3 - int(3 * score),
                overall_score=min(score, 1.0),
                failed_case_details=[],
            )
            context.evaluation_result = eval_result
            return AgentResult.ok("Evaluation complete", data=eval_result)

        evaluator_agent.run = mock_evaluator_run

        # Mock analyzer to return suggestions
        async def mock_analyzer_run(context):
            from meta_agent.agents.analyzer import AnalysisResult, ImprovementSuggestion

            result = AnalysisResult(
                total_failures=1,
                suggestions=[
                    ImprovementSuggestion(
                        category=FailureCategory.SKILL_NOT_TRIGGERED,
                        priority=1,
                        description="Add trigger phrases",
                        affected_cases=["test_001"],
                    )
                ],
            )
            context.analysis_result = result
            return AgentResult.ok("Analysis complete", data=result)

        analyzer_agent.run = mock_analyzer_run

        # Mock generator to return changes
        async def mock_generator_run(context):
            from meta_agent.agents.generator import GenerationResult

            result = GenerationResult(changes=[], success=True)
            context.generation_result = result
            return AgentResult.ok("No changes needed", data=result)

        generator_agent.run = mock_generator_run

        # Mock reviewer to approve
        async def mock_reviewer_run(context):
            from meta_agent.agents.reviewer import ReviewResult

            result = ReviewResult(items=[], all_approved=True)
            return AgentResult.ok("Review complete", data=result)

        reviewer_agent.run = mock_reviewer_run

        # Create orchestrator
        orchestrator = OrchestratorAgent(
            config=config,
            environment_agent=environment_agent,
            evaluator_agent=evaluator_agent,
            analyzer_agent=analyzer_agent,
            generator_agent=generator_agent,
            reviewer_agent=reviewer_agent,
            dataset_service=dataset_service,
            checkpoints_dir=str(tmp_workspace / ".checkpoints"),
        )

        # Run optimization
        context = AgentContext()
        result = await orchestrator.run(context)

        # Verify results
        assert result.success
        assert result.data is not None
        checkpoint = result.data
        assert checkpoint.best_score >= 0.85  # Should reach target
        assert checkpoint.state == OptimizationState.COMPLETED

    @pytest.mark.asyncio
    async def test_optimization_loop_terminates_at_max_iterations(
        self,
        tmp_workspace,
        config,
        sample_dataset,
        mock_sunnyagent_client,
        mock_langfuse_client,
        file_service,
        mock_git_utils,
        dataset_service,
    ):
        """Test that optimization loop terminates at max iterations."""
        # Modify config for low target that won't be reached
        config.target_score = 0.99
        config.max_iterations = 2

        # Create mock agents
        environment_agent = MagicMock()
        environment_agent.run = AsyncMock(return_value=AgentResult.ok("Environment ready"))
        environment_agent.cleanup = AsyncMock()

        evaluator_agent = MagicMock()
        analyzer_agent = MagicMock()
        generator_agent = MagicMock()
        generator_agent.rollback_change = AsyncMock(return_value=True)
        reviewer_agent = MagicMock()

        # Mock evaluator to return constant low score
        async def mock_evaluator_run(context):
            eval_result = EvaluationResult(
                evaluation_id="eval-const",
                dataset_name="test-dataset",
                dataset_version="v1",
                iteration=1,
                total_cases=3,
                passed_cases=2,
                failed_cases=1,
                overall_score=0.70,  # Never reaches 0.99
                failed_case_details=[],
            )
            context.evaluation_result = eval_result
            return AgentResult.ok("Evaluation complete", data=eval_result)

        evaluator_agent.run = mock_evaluator_run

        # Mock other agents
        async def mock_analyzer_run(context):
            from meta_agent.agents.analyzer import AnalysisResult

            result = AnalysisResult(total_failures=1, suggestions=[])
            context.analysis_result = result
            return AgentResult.ok("Analysis complete", data=result)

        analyzer_agent.run = mock_analyzer_run

        async def mock_generator_run(context):
            from meta_agent.agents.generator import GenerationResult

            result = GenerationResult(changes=[], success=True)
            context.generation_result = result
            return AgentResult.ok("No changes", data=result)

        generator_agent.run = mock_generator_run

        async def mock_reviewer_run(context):
            from meta_agent.agents.reviewer import ReviewResult

            return AgentResult.ok("OK", data=ReviewResult(items=[], all_approved=True))

        reviewer_agent.run = mock_reviewer_run

        # Create orchestrator
        orchestrator = OrchestratorAgent(
            config=config,
            environment_agent=environment_agent,
            evaluator_agent=evaluator_agent,
            analyzer_agent=analyzer_agent,
            generator_agent=generator_agent,
            reviewer_agent=reviewer_agent,
            dataset_service=dataset_service,
            checkpoints_dir=str(tmp_workspace / ".checkpoints"),
        )

        # Run optimization
        context = AgentContext()
        result = await orchestrator.run(context)

        # Should complete (not fail) but not reach target
        assert result.success
        checkpoint = result.data
        assert checkpoint.current_iteration == 2  # Max iterations
        assert checkpoint.best_score < 0.99

    @pytest.mark.asyncio
    async def test_optimization_loop_saves_checkpoints(
        self,
        tmp_workspace,
        config,
        sample_dataset,
        mock_sunnyagent_client,
        mock_langfuse_client,
        file_service,
        mock_git_utils,
        dataset_service,
    ):
        """Test that checkpoints are saved during optimization."""
        config.max_iterations = 1

        # Create mock agents
        environment_agent = MagicMock()
        environment_agent.run = AsyncMock(return_value=AgentResult.ok("Environment ready"))
        environment_agent.cleanup = AsyncMock()

        evaluator_agent = MagicMock()
        analyzer_agent = MagicMock()
        generator_agent = MagicMock()
        generator_agent.rollback_change = AsyncMock(return_value=True)
        reviewer_agent = MagicMock()

        # Mock evaluator
        async def mock_evaluator_run(context):
            eval_result = EvaluationResult(
                evaluation_id="eval-1",
                dataset_name="test-dataset",
                dataset_version="v1",
                iteration=1,
                total_cases=3,
                passed_cases=3,
                failed_cases=0,
                overall_score=0.90,
                failed_case_details=[],
            )
            context.evaluation_result = eval_result
            return AgentResult.ok("OK", data=eval_result)

        evaluator_agent.run = mock_evaluator_run

        # Other mocks
        async def mock_analyzer_run(context):
            from meta_agent.agents.analyzer import AnalysisResult

            context.analysis_result = AnalysisResult(total_failures=0, suggestions=[])
            return AgentResult.ok("OK")

        analyzer_agent.run = mock_analyzer_run

        async def mock_generator_run(context):
            from meta_agent.agents.generator import GenerationResult

            context.generation_result = GenerationResult(changes=[], success=True)
            return AgentResult.ok("OK")

        generator_agent.run = mock_generator_run

        async def mock_reviewer_run(context):
            from meta_agent.agents.reviewer import ReviewResult

            return AgentResult.ok("OK", data=ReviewResult(items=[], all_approved=True))

        reviewer_agent.run = mock_reviewer_run

        # Create orchestrator
        orchestrator = OrchestratorAgent(
            config=config,
            environment_agent=environment_agent,
            evaluator_agent=evaluator_agent,
            analyzer_agent=analyzer_agent,
            generator_agent=generator_agent,
            reviewer_agent=reviewer_agent,
            dataset_service=dataset_service,
            checkpoints_dir=str(tmp_workspace / ".checkpoints"),
        )

        # Run optimization
        context = AgentContext()
        result = await orchestrator.run(context)

        # Check checkpoint was saved
        checkpoints_dir = tmp_workspace / ".checkpoints"
        checkpoint_files = list(checkpoints_dir.glob("*.json"))
        assert len(checkpoint_files) >= 1

        # Verify checkpoint content
        with open(checkpoint_files[0]) as f:
            checkpoint_data = json.load(f)
            assert "optimization_id" in checkpoint_data
            assert "best_score" in checkpoint_data

    @pytest.mark.asyncio
    async def test_optimization_can_resume_from_checkpoint(
        self,
        tmp_workspace,
        config,
        dataset_service,
    ):
        """Test that optimization can resume from a saved checkpoint."""
        from meta_agent.models.optimization import Checkpoint

        # Create a checkpoint file
        checkpoint = Checkpoint(
            optimization_id="resume-test-id",
            config=config,
            current_iteration=1,
            best_score=0.75,
            best_iteration=1,
            score_history=[0.75],
            state=OptimizationState.IN_PROGRESS,
        )

        checkpoint_file = tmp_workspace / ".checkpoints" / "resume-test-id.json"
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint.model_dump(mode="json"), f, default=str)

        # Load checkpoint
        loaded = OrchestratorAgent.load_checkpoint(
            "resume-test-id",
            str(tmp_workspace / ".checkpoints"),
        )

        assert loaded is not None
        assert loaded.optimization_id == "resume-test-id"
        assert loaded.current_iteration == 1
        assert loaded.best_score == 0.75
