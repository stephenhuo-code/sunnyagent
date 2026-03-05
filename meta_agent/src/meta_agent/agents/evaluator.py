"""Evaluator Agent - executes tests and calculates scores."""

from __future__ import annotations

from datetime import datetime

from meta_agent.agents.base import BaseAgent, AgentContext, AgentResult
from meta_agent.models.dataset import TestDataset
from meta_agent.models.evaluation import EvaluationResult
from meta_agent.services.evaluation_service import EvaluationService


class EvaluatorAgent(BaseAgent[EvaluationResult]):
    """Agent responsible for executing tests and calculating scores.

    Tasks:
    - Execute test cases via SunnyAgent API
    - Read traces from Langfuse
    - Calculate dimension scores
    - Write scores to Langfuse
    """

    def __init__(
        self,
        evaluation_service: EvaluationService,
        api_key: str | None = None,
    ):
        """
        Initialize evaluator agent.

        Args:
            evaluation_service: Evaluation service
            api_key: Anthropic API key (optional)
        """
        super().__init__(
            name="Evaluator",
            description="Executes tests and calculates scores using Langfuse",
            api_key=api_key,
        )
        self.evaluation_service = evaluation_service

    async def run(self, context: AgentContext) -> AgentResult:
        """
        Execute evaluation.

        Args:
            context: Agent context with dataset and project info

        Returns:
            Result with EvaluationResult
        """
        start_time = datetime.now()
        self.log(f"Starting evaluation for iteration {context.iteration}")

        try:
            # Get dataset from context
            dataset: TestDataset | None = context.metadata.get("dataset")
            if not dataset:
                return AgentResult.fail("No dataset provided in context")

            # Get test files from context
            files = context.metadata.get("test_files", [])

            # Run evaluation
            result = await self.evaluation_service.run_evaluation(
                dataset=dataset,
                project_name=context.project_name,
                iteration=context.iteration,
                files=files,
            )

            # Store result in context
            context.evaluation_result = result

            duration = (datetime.now() - start_time).total_seconds()
            self.log(
                f"Evaluation complete: {result.passed_cases}/{result.total_cases} passed, "
                f"score: {result.overall_score:.2f}"
            )

            return AgentResult.ok(
                message=f"Evaluation complete: score={result.overall_score:.2f}",
                data=result,
            )

        except Exception as e:
            self.log(f"Evaluation failed: {e}", "error")
            return AgentResult.fail(str(e))

    async def run_quick_evaluation(
        self,
        context: AgentContext,
        case_ids: list[str] | None = None,
    ) -> AgentResult:
        """
        Run quick evaluation on subset of cases.

        Args:
            context: Agent context
            case_ids: Optional list of case IDs to evaluate

        Returns:
            Result with partial evaluation
        """
        dataset: TestDataset | None = context.metadata.get("dataset")
        if not dataset:
            return AgentResult.fail("No dataset provided in context")

        # Filter cases if case_ids provided
        if case_ids:
            filtered_cases = [c for c in dataset.cases if c.case_id in case_ids]
            if not filtered_cases:
                return AgentResult.fail("No matching cases found")

            # Create subset dataset
            subset = TestDataset(
                name=f"{dataset.name}-subset",
                plugin_name=dataset.plugin_name,
                cases=filtered_cases,
                version=dataset.version,
            )
            context.metadata["dataset"] = subset

        return await self.run(context)
