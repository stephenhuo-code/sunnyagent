"""Unit tests for ReportGenerator."""

from __future__ import annotations

import pytest
from pathlib import Path

from meta_agent.utils.report_generator import ReportGenerator
from meta_agent.models.optimization import (
    OptimizationConfig,
    Checkpoint,
    OptimizationState,
    IterationReport,
    FileModification,
)
from meta_agent.models.evaluation import EvaluationResult, FailedCase, FailureCategory


class TestReportGenerator:
    """Tests for ReportGenerator."""

    @pytest.fixture
    def generator(self, tmp_path) -> ReportGenerator:
        """Create a ReportGenerator instance."""
        return ReportGenerator(output_dir=str(tmp_path / "reports"))

    @pytest.fixture
    def sample_config(self) -> OptimizationConfig:
        """Create a sample configuration."""
        return OptimizationConfig(
            target_plugin="test-plugin",
            dataset_path="test.jsonl",
            target_score=0.85,
            max_iterations=5,
        )

    @pytest.fixture
    def sample_checkpoint(self, sample_config) -> Checkpoint:
        """Create a sample checkpoint."""
        return Checkpoint(
            optimization_id="test-id-123",
            config=sample_config,
            current_iteration=3,
            best_score=0.82,
            best_iteration=3,
            state=OptimizationState.COMPLETED,
            score_history=[0.65, 0.75, 0.82],
            modified_files=[
                FileModification(
                    file_path="packages/test-plugin/commands/analysis.md",
                    modification_type="update",
                    git_commit_hash="abc1234567890",
                    iteration=2,
                ),
                FileModification(
                    file_path="packages/test-plugin/skills/data-profiler/SKILL.md",
                    modification_type="update",
                    git_commit_hash="def1234567890",
                    iteration=3,
                ),
            ],
        )

    @pytest.fixture
    def sample_iteration_reports(self) -> list[IterationReport]:
        """Create sample iteration reports."""
        return [
            IterationReport(
                iteration=1,
                optimization_id="test-id-123",
                score_before=0.0,
                score_after=0.65,
                score_delta=0.65,
                decision="continue",
                evaluation_id="eval-1",
                langfuse_evaluation_url="https://langfuse.example.com/eval/1",
            ),
            IterationReport(
                iteration=2,
                optimization_id="test-id-123",
                score_before=0.65,
                score_after=0.75,
                score_delta=0.10,
                decision="continue",
                evaluation_id="eval-2",
                analysis_summary="Found 3 skill trigger failures",
            ),
            IterationReport(
                iteration=3,
                optimization_id="test-id-123",
                score_before=0.75,
                score_after=0.82,
                score_delta=0.07,
                decision="terminate",
                decision_reason="Target score approached",
                evaluation_id="eval-3",
            ),
        ]

    # Report Generation Tests

    def test_generate_final_report_creates_file(
        self, generator: ReportGenerator, sample_checkpoint, tmp_path
    ):
        """Test that generate_final_report creates a report file."""
        report_path = generator.generate_final_report(sample_checkpoint)

        assert Path(report_path).exists()
        assert report_path.endswith(".md")

    def test_generate_final_report_contains_summary(
        self, generator: ReportGenerator, sample_checkpoint
    ):
        """Test that report contains summary section."""
        report_path = generator.generate_final_report(sample_checkpoint)

        content = Path(report_path).read_text()

        assert "# Meta-Agent Optimization Report" in content
        assert "## Summary" in content
        assert "test-plugin" in content
        assert "0.82" in content  # best_score

    def test_generate_final_report_contains_score_history(
        self, generator: ReportGenerator, sample_checkpoint
    ):
        """Test that report contains score history."""
        report_path = generator.generate_final_report(sample_checkpoint)

        content = Path(report_path).read_text()

        assert "## Score History" in content
        assert "Iteration 1: 0.650" in content
        assert "Iteration 3: 0.820" in content
        # Best iteration marker
        assert "🏆" in content

    def test_generate_final_report_contains_file_changes(
        self, generator: ReportGenerator, sample_checkpoint
    ):
        """Test that report contains file changes."""
        report_path = generator.generate_final_report(sample_checkpoint)

        content = Path(report_path).read_text()

        assert "## File Changes" in content
        assert "commands/analysis.md" in content
        assert "skills/data-profiler/SKILL.md" in content
        assert "abc1234" in content  # commit hash truncated

    def test_generate_final_report_with_iteration_reports(
        self, generator: ReportGenerator, sample_checkpoint, sample_iteration_reports
    ):
        """Test that report includes iteration details."""
        report_path = generator.generate_final_report(
            sample_checkpoint, sample_iteration_reports
        )

        content = Path(report_path).read_text()

        assert "## Iteration Details" in content
        assert "### Iteration 1" in content
        assert "### Iteration 2" in content
        assert "View in Langfuse" in content
        assert "Found 3 skill trigger failures" in content

    def test_generate_final_report_contains_configuration(
        self, generator: ReportGenerator, sample_checkpoint
    ):
        """Test that report contains configuration."""
        report_path = generator.generate_final_report(sample_checkpoint)

        content = Path(report_path).read_text()

        assert "## Configuration" in content
        assert "target_plugin: test-plugin" in content
        assert "target_score: 0.85" in content

    def test_generate_final_report_with_error(
        self, generator: ReportGenerator, sample_config
    ):
        """Test that report includes error message when failed."""
        checkpoint = Checkpoint(
            optimization_id="failed-id",
            config=sample_config,
            state=OptimizationState.FAILED,
            error_message="Test failure reason",
        )

        report_path = generator.generate_final_report(checkpoint)

        content = Path(report_path).read_text()

        assert "## Error" in content
        assert "Test failure reason" in content

    # Iteration Summary Tests

    def test_generate_iteration_summary(self, generator: ReportGenerator):
        """Test generating iteration summary."""
        evaluation = EvaluationResult(
            evaluation_id="eval-test",
            dataset_name="test-dataset",
            dataset_version="v1",
            iteration=1,
            total_cases=10,
            passed_cases=7,
            failed_cases=3,
            overall_score=0.70,
            duration_seconds=45.5,
        )

        summary = generator.generate_iteration_summary(evaluation, iteration=1)

        assert "## Iteration 1 Summary" in summary
        assert "0.70" in summary
        assert "70.0%" in summary
        assert "7/10" in summary

    def test_generate_iteration_summary_with_failures(self, generator: ReportGenerator):
        """Test iteration summary includes failure details."""
        failed_cases = [
            FailedCase(
                case_id="test_001",
                actual_output="wrong output",
                failure_category=FailureCategory.SKILL_NOT_TRIGGERED,
                failure_reason="Skill not triggered",
            ),
            FailedCase(
                case_id="test_002",
                actual_output="partial output",
                failure_category=FailureCategory.OUTPUT_INCOMPLETE,
                failure_reason="Missing data",
            ),
        ]

        evaluation = EvaluationResult(
            evaluation_id="eval-test",
            dataset_name="test-dataset",
            dataset_version="v1",
            iteration=1,
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            failed_case_details=failed_cases,
            overall_score=0.80,
            duration_seconds=30.0,
        )

        summary = generator.generate_iteration_summary(evaluation, iteration=1)

        assert "### Top Failures" in summary
        assert "test_001" in summary
        assert "skill_not_triggered" in summary
