"""Unit tests for OrchestratorAgent."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from meta_agent.agents.orchestrator import OrchestratorAgent
from meta_agent.agents.base import AgentContext, AgentResult
from meta_agent.models.optimization import OptimizationConfig, Checkpoint, OptimizationState


class TestOrchestratorAgent:
    """Tests for OrchestratorAgent."""

    @pytest.fixture
    def mock_environment_agent(self):
        """Create a mock EnvironmentSetupAgent."""
        agent = MagicMock()
        agent.run = AsyncMock(return_value=AgentResult.ok("Environment ready"))
        agent.cleanup = AsyncMock()
        return agent

    @pytest.fixture
    def mock_evaluator_agent(self):
        """Create a mock EvaluatorAgent."""
        from meta_agent.models.evaluation import EvaluationResult

        evaluator = MagicMock()
        evaluator.run = AsyncMock(
            return_value=AgentResult.ok(
                "Evaluation complete",
                data=EvaluationResult(
                    evaluation_id="eval-123",
                    dataset_name="test-dataset",
                    dataset_version="v1",
                    iteration=1,
                    total_cases=10,
                    passed_cases=7,
                    failed_cases=3,
                    overall_score=0.7,
                ),
            )
        )
        return evaluator

    @pytest.fixture
    def mock_analyzer_agent(self):
        """Create a mock AnalyzerAgent."""
        from meta_agent.agents.analyzer import AnalysisResult

        analyzer = MagicMock()
        analyzer.run = AsyncMock(
            return_value=AgentResult.ok(
                "Analysis complete",
                data=AnalysisResult(
                    total_failures=3,
                    suggestions=[],
                ),
            )
        )
        return analyzer

    @pytest.fixture
    def mock_generator_agent(self):
        """Create a mock GeneratorAgent."""
        from meta_agent.agents.generator import GenerationResult

        generator = MagicMock()
        generator.run = AsyncMock(
            return_value=AgentResult.ok(
                "Generation complete",
                data=GenerationResult(
                    changes=[],
                    success=True,
                ),
            )
        )
        generator.rollback_change = AsyncMock(return_value=True)
        return generator

    @pytest.fixture
    def mock_reviewer_agent(self):
        """Create a mock ReviewerAgent."""
        from meta_agent.agents.reviewer import ReviewResult

        reviewer = MagicMock()
        reviewer.run = AsyncMock(
            return_value=AgentResult.ok(
                "Review complete",
                data=ReviewResult(items=[], all_approved=True),
            )
        )
        return reviewer

    @pytest.fixture
    def mock_dataset_service(self):
        """Create a mock DatasetService."""
        from meta_agent.models.dataset import TestDataset

        service = MagicMock()
        service.load_dataset = MagicMock(
            return_value=TestDataset(
                name="test-dataset",
                version="v1",
                plugin_name="test-plugin",
                cases=[],
                source_file="test.jsonl",
            )
        )
        return service

    @pytest.fixture
    def config(self) -> OptimizationConfig:
        """Create a test configuration."""
        return OptimizationConfig(
            target_plugin="test-plugin",
            dataset_path="test.jsonl",
            target_score=0.85,
            max_iterations=5,
            patience=2,
            regression_threshold=0.05,
        )

    # Config Termination Tests

    def test_config_should_terminate_target_reached(self, config: OptimizationConfig):
        """Test termination when target score is reached."""
        should_stop, reason = config.should_terminate(
            current_score=0.90,  # Above target of 0.85
            current_iteration=1,
            no_improvement_count=0,
        )

        assert should_stop
        assert "target" in reason.lower()

    def test_config_should_terminate_max_iterations(self, config: OptimizationConfig):
        """Test termination when max iterations reached."""
        should_stop, reason = config.should_terminate(
            current_score=0.70,
            current_iteration=5,  # Max iterations
            no_improvement_count=0,
        )

        assert should_stop
        assert "iteration" in reason.lower()

    def test_config_should_terminate_patience_exceeded(self, config: OptimizationConfig):
        """Test termination when patience is exceeded."""
        should_stop, reason = config.should_terminate(
            current_score=0.70,
            current_iteration=3,
            no_improvement_count=3,  # Exceeds patience of 2
        )

        assert should_stop
        assert "patience" in reason.lower() or "improvement" in reason.lower()

    def test_config_should_not_terminate_ongoing(self, config: OptimizationConfig):
        """Test no termination when optimization should continue."""
        should_stop, reason = config.should_terminate(
            current_score=0.70,
            current_iteration=2,
            no_improvement_count=1,
        )

        assert not should_stop

    # Checkpoint Tests

    def test_save_and_load_checkpoint(self, tmp_path):
        """Test saving and loading a checkpoint."""
        from meta_agent.models.optimization import OptimizationConfig, Checkpoint

        config = OptimizationConfig(
            target_plugin="test-plugin",
            dataset_path="test.jsonl",
        )

        checkpoint = Checkpoint(
            optimization_id="test-id",
            config=config,
            current_iteration=2,
            best_score=0.75,
        )

        # Save
        checkpoint_file = tmp_path / "test-id.json"
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint.model_dump(mode="json"), f, default=str)

        # Load
        loaded = OrchestratorAgent.load_checkpoint("test-id", str(tmp_path))

        assert loaded is not None
        assert loaded.optimization_id == "test-id"
        assert loaded.current_iteration == 2
        assert loaded.best_score == 0.75

    def test_load_nonexistent_checkpoint(self, tmp_path):
        """Test loading a non-existent checkpoint returns None."""
        loaded = OrchestratorAgent.load_checkpoint("nonexistent-id", str(tmp_path))
        assert loaded is None

    def test_list_checkpoints(self, tmp_path):
        """Test listing available checkpoints."""
        from meta_agent.models.optimization import OptimizationConfig, Checkpoint

        config = OptimizationConfig(
            target_plugin="test-plugin",
            dataset_path="test.jsonl",
        )

        # Create some checkpoints
        for i in range(3):
            checkpoint = Checkpoint(
                optimization_id=f"test-id-{i}",
                config=config,
                current_iteration=i + 1,
                best_score=0.70 + i * 0.05,
            )
            checkpoint_file = tmp_path / f"test-id-{i}.json"
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint.model_dump(mode="json"), f, default=str)

        checkpoints = OrchestratorAgent.list_checkpoints(str(tmp_path))

        assert len(checkpoints) == 3

    # Checkpoint Regression Detection Tests

    def test_checkpoint_is_regression(self, config: OptimizationConfig):
        """Test checkpoint regression detection."""
        checkpoint = Checkpoint(
            optimization_id="test-id",
            config=config,
            best_score=0.80,
            score_history=[0.80],  # Need score history for regression check
        )

        # Score drop of 0.10 exceeds threshold of 0.05
        assert checkpoint.is_regression(0.70) is True

    def test_checkpoint_no_regression_small_drop(self, config: OptimizationConfig):
        """Test no regression for small score drop."""
        checkpoint = Checkpoint(
            optimization_id="test-id",
            config=config,
            best_score=0.80,
            score_history=[0.80],  # Need score history for regression check
        )

        # Score drop of 0.02 is within threshold
        assert checkpoint.is_regression(0.78) is False

    def test_checkpoint_no_regression_improvement(self, config: OptimizationConfig):
        """Test no regression when score improves."""
        checkpoint = Checkpoint(
            optimization_id="test-id",
            config=config,
            best_score=0.75,
            score_history=[0.75],  # Need score history for regression check
        )

        assert checkpoint.is_regression(0.80) is False

    def test_checkpoint_no_regression_empty_history(self, config: OptimizationConfig):
        """Test no regression when history is empty."""
        checkpoint = Checkpoint(
            optimization_id="test-id",
            config=config,
            best_score=0.80,
        )

        # Empty history means no regression
        assert checkpoint.is_regression(0.50) is False

    # Checkpoint Progress Update Tests

    def test_checkpoint_update_progress_improvement(self, config: OptimizationConfig):
        """Test updating progress with improvement."""
        checkpoint = Checkpoint(
            optimization_id="test-id",
            config=config,
            current_iteration=1,
            best_score=0.70,
        )

        checkpoint.update_progress(0.80, "eval-123")

        assert checkpoint.current_iteration == 2
        assert checkpoint.best_score == 0.80
        assert checkpoint.no_improvement_count == 0

    def test_checkpoint_update_progress_no_improvement(self, config: OptimizationConfig):
        """Test updating progress without improvement."""
        checkpoint = Checkpoint(
            optimization_id="test-id",
            config=config,
            current_iteration=1,
            best_score=0.80,
            best_iteration=1,
        )

        checkpoint.update_progress(0.75, "eval-123")

        assert checkpoint.current_iteration == 2
        assert checkpoint.best_score == 0.80  # Unchanged
        assert checkpoint.no_improvement_count == 1
