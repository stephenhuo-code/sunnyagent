"""Unit tests for ScoreCalculator."""

from __future__ import annotations

import pytest

from meta_agent.utils.score_calculator import ScoreCalculator
from meta_agent.models.evaluation import CaseScore


class TestScoreCalculator:
    """Tests for ScoreCalculator."""

    @pytest.fixture
    def calculator(self) -> ScoreCalculator:
        """Create a score calculator instance."""
        return ScoreCalculator()

    def test_calculate_correctness_empty_expected(self, calculator: ScoreCalculator):
        """Test correctness with empty expected_contains returns 1.0."""
        score = calculator.calculate_correctness("any response", [])
        assert score == 1.0

    def test_calculate_correctness_all_match(self, calculator: ScoreCalculator):
        """Test correctness with all keywords matching."""
        response = "The CPK value is 1.33 and 合格率 is 95%"
        expected = ["CPK", "合格率"]
        score = calculator.calculate_correctness(response, expected)
        assert score == 1.0

    def test_calculate_correctness_partial_match(self, calculator: ScoreCalculator):
        """Test correctness with partial matching."""
        response = "The CPK value is 1.33"
        expected = ["CPK", "合格率", "异常"]
        score = calculator.calculate_correctness(response, expected)
        assert score == pytest.approx(1 / 3, rel=0.01)

    def test_calculate_correctness_no_match(self, calculator: ScoreCalculator):
        """Test correctness with no matching keywords."""
        response = "No relevant information"
        expected = ["CPK", "合格率"]
        score = calculator.calculate_correctness(response, expected)
        assert score == 0.0

    def test_calculate_skill_trigger_no_expected(self, calculator: ScoreCalculator):
        """Test skill trigger with no expected skill."""
        score = calculator.calculate_skill_trigger("any-skill", None)
        assert score == 1.0

    def test_calculate_skill_trigger_match(self, calculator: ScoreCalculator):
        """Test skill trigger with matching skill."""
        score = calculator.calculate_skill_trigger("data-profiler", "data-profiler")
        assert score == 1.0

    def test_calculate_skill_trigger_mismatch(self, calculator: ScoreCalculator):
        """Test skill trigger with mismatching skill."""
        score = calculator.calculate_skill_trigger("wrong-skill", "data-profiler")
        assert score == 0.0

    def test_calculate_skill_trigger_none_actual(self, calculator: ScoreCalculator):
        """Test skill trigger when no skill was triggered."""
        score = calculator.calculate_skill_trigger(None, "data-profiler")
        assert score == 0.0

    def test_calculate_file_context_empty_expected(self, calculator: ScoreCalculator):
        """Test file context with empty expected files."""
        score = calculator.calculate_file_context_usage(["any.csv"], [])
        assert score == 1.0

    def test_calculate_file_context_all_used(self, calculator: ScoreCalculator):
        """Test file context with all expected files used."""
        used = ["data/quality.csv", "data/report.xlsx"]
        expected = ["quality.csv", "report.xlsx"]
        score = calculator.calculate_file_context_usage(used, expected)
        assert score == 1.0

    def test_calculate_file_context_partial(self, calculator: ScoreCalculator):
        """Test file context with partial file usage."""
        used = ["data/quality.csv"]
        expected = ["quality.csv", "report.xlsx"]
        score = calculator.calculate_file_context_usage(used, expected)
        assert score == 0.5

    def test_calculate_overall_weights(self, calculator: ScoreCalculator):
        """Test overall score calculation with correct weights."""
        scores = CaseScore(
            correctness=1.0,
            skill_trigger=1.0,
            response_quality=1.0,
            file_context_usage=1.0,
        )
        overall = calculator.calculate_overall(scores)
        # 0.50 + 0.167 + 0.167 + 0.167 = 1.001 (rounding)
        assert overall == pytest.approx(1.0, rel=0.01)

    def test_calculate_overall_correctness_weight(self, calculator: ScoreCalculator):
        """Test that correctness has 50% weight."""
        scores = CaseScore(
            correctness=1.0,
            skill_trigger=0.0,
            response_quality=0.0,
            file_context_usage=0.0,
        )
        overall = calculator.calculate_overall(scores)
        assert overall == pytest.approx(0.5, rel=0.01)

    def test_calculate_case_score_integration(self, calculator: ScoreCalculator):
        """Test full case score calculation."""
        scores = calculator.calculate_case_score(
            response="分析结果显示 CPK 值为 1.33，合格率达到 95%",
            actual_skill="data-profiler",
            expected_skill="data-profiler",
            expected_contains=["CPK", "合格率"],
            used_files=["data/quality.csv"],
            expected_files=["quality.csv"],
            response_quality=0.8,
        )

        assert scores.correctness == 1.0
        assert scores.skill_trigger == 1.0
        assert scores.file_context_usage == 1.0
        assert scores.response_quality == 0.8
        assert scores.overall > 0.9

    def test_aggregate_scores_empty(self, calculator: ScoreCalculator):
        """Test aggregation with empty list."""
        result = calculator.aggregate_scores([])
        assert result["overall"] == 0.0

    def test_aggregate_scores_multiple(self, calculator: ScoreCalculator):
        """Test aggregation of multiple scores."""
        scores = [
            CaseScore(correctness=1.0, skill_trigger=1.0, response_quality=1.0, file_context_usage=1.0, overall=1.0),
            CaseScore(correctness=0.5, skill_trigger=0.5, response_quality=0.5, file_context_usage=0.5, overall=0.5),
        ]
        result = calculator.aggregate_scores(scores)
        assert result["correctness"] == 0.75
        assert result["overall"] == 0.75
