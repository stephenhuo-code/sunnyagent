"""Analyzer Agent - analyzes failures and generates suggestions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from meta_agent.agents.base import BaseAgent, AgentContext, AgentResult
from meta_agent.models.evaluation import EvaluationResult, FailedCase, FailureCategory


@dataclass
class ImprovementSuggestion:
    """Improvement suggestion from analysis."""

    category: FailureCategory
    priority: int  # 1 = highest
    description: str
    affected_cases: list[str] = field(default_factory=list)
    suggested_changes: list[dict[str, Any]] = field(default_factory=list)
    estimated_impact: float = 0.0  # Expected score improvement


@dataclass
class AnalysisResult:
    """Result of failure analysis."""

    total_failures: int
    failures_by_category: dict[str, int] = field(default_factory=dict)
    suggestions: list[ImprovementSuggestion] = field(default_factory=list)
    summary: str = ""


class AnalyzerAgent(BaseAgent[AnalysisResult]):
    """Agent responsible for analyzing failures and generating suggestions.

    Tasks:
    - Read failed case details from Langfuse
    - Categorize failures by type
    - Identify file-related failures
    - Generate prioritized improvement suggestions
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize analyzer agent.

        Args:
            api_key: Anthropic API key (optional)
        """
        super().__init__(
            name="Analyzer",
            description="Analyzes failures and generates improvement suggestions",
            api_key=api_key,
        )

    async def run(self, context: AgentContext) -> AgentResult:
        """
        Analyze evaluation results.

        Args:
            context: Agent context with evaluation_result

        Returns:
            Result with AnalysisResult
        """
        start_time = datetime.now()
        self.log("Analyzing evaluation results")

        evaluation: EvaluationResult | None = context.evaluation_result
        if not evaluation:
            return AgentResult.fail("No evaluation result in context")

        try:
            # Categorize failures
            failures_by_category = self._categorize_failures(
                evaluation.failed_case_details
            )

            # Generate suggestions using LLM
            suggestions = await self._generate_suggestions(
                evaluation.failed_case_details,
                context.plugin_name,
            )

            # Create summary
            summary = await self._generate_summary(
                evaluation,
                failures_by_category,
                suggestions,
            )

            result = AnalysisResult(
                total_failures=len(evaluation.failed_case_details),
                failures_by_category={k.value: v for k, v in failures_by_category.items()},
                suggestions=suggestions,
                summary=summary,
            )

            # Store in context
            context.analysis_result = result

            duration = (datetime.now() - start_time).total_seconds()
            self.log(
                f"Analysis complete: {len(suggestions)} suggestions generated"
            )

            return AgentResult.ok(
                message=f"Generated {len(suggestions)} improvement suggestions",
                data=result,
            )

        except Exception as e:
            self.log(f"Analysis failed: {e}", "error")
            return AgentResult.fail(str(e))

    def _categorize_failures(
        self,
        failed_cases: list[FailedCase],
    ) -> dict[FailureCategory, int]:
        """Categorize failures by type."""
        categories: dict[FailureCategory, int] = {}
        for case in failed_cases:
            category = case.failure_category
            categories[category] = categories.get(category, 0) + 1
        return categories

    async def _generate_suggestions(
        self,
        failed_cases: list[FailedCase],
        plugin_name: str,
    ) -> list[ImprovementSuggestion]:
        """Generate improvement suggestions using LLM."""
        if not failed_cases:
            return []

        # Group by category for analysis
        by_category: dict[FailureCategory, list[FailedCase]] = {}
        for case in failed_cases:
            category = case.failure_category
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(case)

        suggestions = []

        for category, cases in by_category.items():
            # Build prompt for LLM analysis
            case_summaries = []
            for case in cases[:5]:  # Limit to 5 examples per category
                case_summaries.append(
                    f"- Case {case.case_id}: {case.failure_reason}"
                )

            prompt = f"""Analyze these test failures for plugin "{plugin_name}" and suggest improvements.

Failure Category: {category.value}
Number of failures: {len(cases)}

Example failures:
{chr(10).join(case_summaries)}

Provide a concise improvement suggestion that addresses the root cause.
Focus on specific changes to Commands or Skills that would fix these failures.
"""

            try:
                response = await self.call_llm(
                    system_prompt="You are a plugin optimization expert. Analyze test failures and suggest specific improvements.",
                    user_message=prompt,
                    max_tokens=1024,
                )

                suggestion = ImprovementSuggestion(
                    category=category,
                    priority=self._calculate_priority(category, len(cases)),
                    description=response.strip(),
                    affected_cases=[c.case_id for c in cases],
                    estimated_impact=self._estimate_impact(category, len(cases), len(failed_cases)),
                )
                suggestions.append(suggestion)

            except Exception as e:
                self.log(f"Failed to generate suggestion for {category}: {e}", "warning")
                # Add a basic suggestion without LLM
                suggestion = ImprovementSuggestion(
                    category=category,
                    priority=self._calculate_priority(category, len(cases)),
                    description=f"Fix {category.value} issues affecting {len(cases)} cases",
                    affected_cases=[c.case_id for c in cases],
                )
                suggestions.append(suggestion)

        # Sort by priority
        suggestions.sort(key=lambda s: s.priority)
        return suggestions

    def _calculate_priority(self, category: FailureCategory, count: int) -> int:
        """Calculate priority based on category and frequency."""
        # Base priority by category
        category_priority = {
            FailureCategory.SKILL_NOT_TRIGGERED: 1,
            FailureCategory.WRONG_SKILL_TRIGGERED: 2,
            FailureCategory.OUTPUT_INCORRECT: 3,
            FailureCategory.OUTPUT_INCOMPLETE: 4,
            FailureCategory.FILE_CONTEXT_ERROR: 5,
            FailureCategory.EXECUTION_ERROR: 6,
            FailureCategory.TIMEOUT: 7,
        }

        base = category_priority.get(category, 5)

        # Adjust for frequency (more failures = higher priority)
        if count >= 10:
            return max(1, base - 2)
        elif count >= 5:
            return max(1, base - 1)
        return base

    def _estimate_impact(
        self,
        category: FailureCategory,
        category_count: int,
        total_failures: int,
    ) -> float:
        """Estimate score improvement if category is fixed."""
        if total_failures == 0:
            return 0.0

        # Proportion of failures in this category
        proportion = category_count / total_failures

        # Weight by category importance
        importance = {
            FailureCategory.SKILL_NOT_TRIGGERED: 1.0,
            FailureCategory.WRONG_SKILL_TRIGGERED: 0.9,
            FailureCategory.OUTPUT_INCORRECT: 0.8,
            FailureCategory.OUTPUT_INCOMPLETE: 0.6,
            FailureCategory.FILE_CONTEXT_ERROR: 0.5,
            FailureCategory.EXECUTION_ERROR: 0.4,
            FailureCategory.TIMEOUT: 0.3,
        }

        weight = importance.get(category, 0.5)
        return proportion * weight * 0.2  # Max 20% improvement per category

    async def _generate_summary(
        self,
        evaluation: EvaluationResult,
        failures_by_category: dict[FailureCategory, int],
        suggestions: list[ImprovementSuggestion],
    ) -> str:
        """Generate analysis summary."""
        lines = [
            f"## Analysis Summary",
            f"",
            f"**Overall Score**: {evaluation.overall_score:.2f}",
            f"**Pass Rate**: {evaluation.pass_rate:.1%}",
            f"**Failed Cases**: {evaluation.failed_cases}/{evaluation.total_cases}",
            f"",
            f"### Failure Distribution",
        ]

        for category, count in sorted(
            failures_by_category.items(),
            key=lambda x: -x[1],
        ):
            lines.append(f"- {category.value}: {count}")

        if suggestions:
            lines.extend([
                f"",
                f"### Top Priorities",
            ])
            for i, suggestion in enumerate(suggestions[:3], 1):
                lines.append(
                    f"{i}. [{suggestion.category.value}] "
                    f"Impact: {suggestion.estimated_impact:.1%}"
                )

        return "\n".join(lines)
