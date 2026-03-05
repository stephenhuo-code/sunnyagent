"""Score calculation utilities."""

from __future__ import annotations

from typing import Any

from meta_agent.models.evaluation import CaseScore


class ScoreCalculator:
    """Score calculator for evaluation results.

    Weights:
        - correctness: 50%
        - skill_trigger: 16.7%
        - response_quality: 16.7%
        - file_context_usage: 16.7%
    """

    WEIGHT_CORRECTNESS = 0.50
    WEIGHT_SKILL_TRIGGER = 0.167
    WEIGHT_RESPONSE_QUALITY = 0.167
    WEIGHT_FILE_CONTEXT_USAGE = 0.167

    def calculate_correctness(
        self,
        response: str,
        expected_contains: list[str],
    ) -> float:
        """
        Calculate output correctness.

        Logic:
            - If expected_contains is empty, return 1.0
            - Otherwise calculate the ratio of matched keywords

        Args:
            response: Actual response content
            expected_contains: List of expected keywords

        Returns:
            Score [0, 1]
        """
        if not expected_contains:
            return 1.0

        matched = sum(1 for kw in expected_contains if kw in response)
        return matched / len(expected_contains)

    def calculate_skill_trigger(
        self,
        actual_skill: str | None,
        expected_skill: str | None,
    ) -> float:
        """
        Calculate skill trigger correctness.

        Logic:
            - If expected_skill is empty, return 1.0
            - If matched, return 1.0
            - Otherwise return 0.0

        Args:
            actual_skill: Actually triggered skill
            expected_skill: Expected skill name

        Returns:
            Score [0, 1]
        """
        if not expected_skill:
            return 1.0
        return 1.0 if actual_skill == expected_skill else 0.0

    def calculate_file_context_usage(
        self,
        used_files: list[str],
        expected_files: list[str],
    ) -> float:
        """
        Calculate file context usage correctness.

        Logic:
            - If expected_files is empty, return 1.0
            - Check if expected files were used
            - Return ratio of matched files

        Args:
            used_files: Files actually used in execution
            expected_files: Expected files to be used

        Returns:
            Score [0, 1]
        """
        if not expected_files:
            return 1.0

        # Normalize file paths for comparison
        used_set = {f.lower().replace("\\", "/") for f in used_files}
        matched = 0
        for f in expected_files:
            normalized = f.lower().replace("\\", "/")
            # Check if any used file contains or matches the expected file
            if any(normalized in used or used.endswith(normalized) for used in used_set):
                matched += 1

        return matched / len(expected_files)

    def calculate_overall(self, scores: CaseScore) -> float:
        """
        Calculate weighted overall score.

        Weights:
            - correctness: 50%
            - skill_trigger: 16.7%
            - response_quality: 16.7%
            - file_context_usage: 16.7%

        Args:
            scores: Case scores

        Returns:
            Overall score [0, 1]
        """
        overall = (
            self.WEIGHT_CORRECTNESS * scores.correctness
            + self.WEIGHT_SKILL_TRIGGER * scores.skill_trigger
            + self.WEIGHT_RESPONSE_QUALITY * scores.response_quality
            + self.WEIGHT_FILE_CONTEXT_USAGE * scores.file_context_usage
        )
        scores.overall = overall
        return overall

    def calculate_case_score(
        self,
        response: str,
        actual_skill: str | None,
        expected_skill: str | None,
        expected_contains: list[str],
        used_files: list[str],
        expected_files: list[str],
        response_quality: float = 1.0,
    ) -> CaseScore:
        """
        Calculate all scores for a test case.

        Args:
            response: Actual response content
            actual_skill: Actually triggered skill
            expected_skill: Expected skill name
            expected_contains: Expected keywords in output
            used_files: Files used during execution
            expected_files: Expected files
            response_quality: Pre-calculated response quality score (from LLM evaluation)

        Returns:
            Complete case scores
        """
        scores = CaseScore(
            correctness=self.calculate_correctness(response, expected_contains),
            skill_trigger=self.calculate_skill_trigger(actual_skill, expected_skill),
            response_quality=response_quality,
            file_context_usage=self.calculate_file_context_usage(
                used_files, expected_files
            ),
        )
        self.calculate_overall(scores)
        return scores

    def aggregate_scores(self, case_scores: list[CaseScore]) -> dict[str, float]:
        """
        Aggregate scores across multiple test cases.

        Args:
            case_scores: List of case scores

        Returns:
            Aggregated scores by dimension
        """
        if not case_scores:
            return {
                "correctness": 0.0,
                "skill_trigger": 0.0,
                "response_quality": 0.0,
                "file_context_usage": 0.0,
                "overall": 0.0,
            }

        n = len(case_scores)
        return {
            "correctness": sum(s.correctness for s in case_scores) / n,
            "skill_trigger": sum(s.skill_trigger for s in case_scores) / n,
            "response_quality": sum(s.response_quality for s in case_scores) / n,
            "file_context_usage": sum(s.file_context_usage for s in case_scores) / n,
            "overall": sum(s.overall for s in case_scores) / n,
        }

    def extract_file_operations(self, trace_data: dict[str, Any]) -> list[str]:
        """
        Extract file operations from trace data.

        Args:
            trace_data: Trace data from Langfuse

        Returns:
            List of file paths that were accessed
        """
        files: list[str] = []

        # Extract from spans
        spans = trace_data.get("spans", [])
        for span in spans:
            # Look for file-related spans
            span_name = span.get("name", "")
            if "file" in span_name.lower() or "read" in span_name.lower():
                input_data = span.get("input", {})
                if isinstance(input_data, dict):
                    file_path = input_data.get("file_path") or input_data.get("path")
                    if file_path:
                        files.append(file_path)

            # Check output for file references
            output_data = span.get("output", {})
            if isinstance(output_data, dict):
                file_path = output_data.get("file_path") or output_data.get("path")
                if file_path:
                    files.append(file_path)

        return list(set(files))
