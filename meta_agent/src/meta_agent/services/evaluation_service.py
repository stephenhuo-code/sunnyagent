"""Evaluation service for running test cases and calculating scores."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from meta_agent.models.dataset import TestCase, TestDataset, TestFile
from meta_agent.models.evaluation import (
    CaseResult,
    CaseScore,
    ChatResponse,
    EvaluationResult,
    FailedCase,
    FailureCategory,
    CaseExecutionError,
    CaseTimeoutError,
)
from meta_agent.services.langfuse_client import LangfuseClient, ScoreInput
from meta_agent.services.sunnyagent_client import (
    SunnyAgentClient,
    ChatTimeoutError as ClientTimeoutError,
    SunnyAgentError,
)
from meta_agent.utils.score_calculator import ScoreCalculator

logger = logging.getLogger(__name__)


# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff in seconds


class EvaluationService:
    """Evaluation service for running tests and calculating scores.

    Handles:
    - Test environment setup
    - Case execution
    - Score calculation
    - Langfuse score writing
    """

    def __init__(
        self,
        sunnyagent_client: SunnyAgentClient,
        langfuse_client: LangfuseClient,
        score_calculator: ScoreCalculator | None = None,
    ):
        """
        Initialize evaluation service.

        Args:
            sunnyagent_client: SunnyAgent API client
            langfuse_client: Langfuse client
            score_calculator: Score calculator (optional)
        """
        self.sunnyagent = sunnyagent_client
        self.langfuse = langfuse_client
        self.calculator = score_calculator or ScoreCalculator()

    async def run_evaluation(
        self,
        dataset: TestDataset,
        project_name: str,
        iteration: int = 0,
        files: list[TestFile] | None = None,
    ) -> EvaluationResult:
        """
        Run complete evaluation.

        Args:
            dataset: Test dataset
            project_name: Test project name
            iteration: Iteration number
            files: Test files to upload

        Returns:
            result: Evaluation result

        Process:
            1. Ensure test project exists
            2. Upload required files
            3. Execute each case
            4. Read trace from Langfuse
            5. Calculate dimension scores
            6. Write scores to Langfuse
            7. Aggregate results
        """
        evaluation_id = str(uuid.uuid4())
        result = EvaluationResult(
            evaluation_id=evaluation_id,
            dataset_name=dataset.name,
            dataset_version=dataset.version,
            iteration=iteration,
            total_cases=len(dataset.cases),
            started_at=datetime.now(),
        )

        try:
            # Setup environment
            project_id, file_id_map = await self.setup_test_environment(
                project_name=project_name,
                files=files or [],
            )

            # Execute cases
            case_scores: list[CaseScore] = []
            for case in dataset.cases:
                case_result = await self._execute_case_with_retry(
                    case=case,
                    project_id=project_id,
                    file_id_map=file_id_map,
                )

                if case_result.passed:
                    result.passed_cases += 1
                    result.passed_case_ids.append(case.case_id)
                else:
                    result.failed_cases += 1
                    result.failed_case_details.append(
                        self._create_failed_case(case, case_result)
                    )

                case_scores.append(case_result.scores)

                # Write scores to Langfuse
                if case_result.response.langfuse_trace_id:
                    await self._write_scores_to_langfuse(
                        trace_id=case_result.response.langfuse_trace_id,
                        scores=case_result.scores,
                    )

            # Aggregate scores
            result.scores_by_dimension = self.calculator.aggregate_scores(case_scores)
            result.overall_score = result.scores_by_dimension.get("overall", 0.0)
            result.complete()

            logger.info(
                f"Evaluation complete: {result.passed_cases}/{result.total_cases} passed, "
                f"overall score: {result.overall_score:.2f}"
            )

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            result.complete()
            raise

        return result

    async def setup_test_environment(
        self,
        project_name: str,
        files: list[TestFile],
    ) -> tuple[str, dict[str, str]]:
        """
        Prepare test environment.

        Args:
            project_name: Project name
            files: Files to upload

        Returns:
            project_id: Project ID
            file_id_map: {relative_path: file_id}
        """
        # Login
        await self.sunnyagent.login()

        # Get or create project
        project = await self.sunnyagent.get_project(project_name)
        if not project:
            project = await self.sunnyagent.create_project(
                name=project_name,
                description="Meta-Agent test project",
            )

        # Upload files
        file_id_map: dict[str, str] = {}
        for test_file in files:
            if test_file.sunnyagent_file_id:
                # Already uploaded
                file_id_map[test_file.relative_path] = test_file.sunnyagent_file_id
            else:
                # Upload file
                # Note: Need absolute path - caller should provide it
                try:
                    file_info = await self.sunnyagent.upload_file(
                        project_id=project.id,
                        file_path=test_file.relative_path,  # Should be absolute
                    )
                    file_id_map[test_file.relative_path] = file_info.id
                    test_file.sunnyagent_file_id = file_info.id
                    test_file.uploaded_to_project = project_name
                except Exception as e:
                    logger.warning(f"Failed to upload {test_file.relative_path}: {e}")

        return project.id, file_id_map

    async def cleanup_test_environment(
        self,
        project_id: str,
        delete_project: bool = False,
    ) -> None:
        """Clean up test environment."""
        if delete_project:
            try:
                await self.sunnyagent.delete_project(project_id)
            except Exception as e:
                logger.warning(f"Failed to delete project: {e}")

        await self.sunnyagent.logout()

    async def run_single_case(
        self,
        case: TestCase,
        project_id: str,
        file_id_map: dict[str, str],
    ) -> CaseResult:
        """
        Run single test case.

        Args:
            case: Test case
            project_id: Project ID
            file_id_map: File path to ID mapping

        Returns:
            result: Case result
        """
        start_time = datetime.now()

        try:
            # Create conversation
            conversation = await self.sunnyagent.create_conversation(
                project_id=project_id,
                title=f"Test: {case.case_id}",
            )

            # Send conversation history first (for multi-turn tests)
            for msg in case.conversation_history:
                if msg.role == "user":
                    await self.sunnyagent.send_message_and_wait(
                        thread_id=conversation.thread_id,
                        message=msg.content,
                        timeout=30.0,
                    )

            # Map context files to file IDs
            file_ids = [
                file_id_map[f]
                for f in case.context_files
                if f in file_id_map
            ]

            # Send test message
            response = await self.sunnyagent.send_message_and_wait(
                thread_id=conversation.thread_id,
                message=case.input,
                file_ids=file_ids if file_ids else None,
                timeout=60.0,
            )

            # Calculate scores
            chat_response = ChatResponse(
                content=response.content,
                tool_calls=response.tool_calls,
                agent_used=response.agent_used,
                skill_used=response.skill_used,
                langfuse_trace_id=response.langfuse_trace_id,
            )

            scores = await self.calculate_case_score(case, chat_response)

            execution_time = (datetime.now() - start_time).total_seconds()

            # Determine pass/fail
            passed = scores.overall >= 0.6  # 60% threshold

            return CaseResult(
                case_id=case.case_id,
                passed=passed,
                response=chat_response,
                scores=scores,
                execution_time=execution_time,
            )

        except ClientTimeoutError as e:
            return CaseResult(
                case_id=case.case_id,
                passed=False,
                response=ChatResponse(),
                scores=CaseScore(),
                error=f"Timeout: {e}",
                execution_time=(datetime.now() - start_time).total_seconds(),
            )
        except SunnyAgentError as e:
            return CaseResult(
                case_id=case.case_id,
                passed=False,
                response=ChatResponse(),
                scores=CaseScore(),
                error=f"Execution error: {e}",
                execution_time=(datetime.now() - start_time).total_seconds(),
            )

    async def _execute_case_with_retry(
        self,
        case: TestCase,
        project_id: str,
        file_id_map: dict[str, str],
    ) -> CaseResult:
        """Execute case with retry logic."""
        for attempt in range(MAX_RETRIES):
            result = await self.run_single_case(case, project_id, file_id_map)

            # Success or non-retryable error
            if result.passed or not result.error:
                return result

            # Check if error is retryable
            if "Timeout" in (result.error or "") or "rate limit" in (result.error or "").lower():
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(
                        f"Case {case.case_id} failed (attempt {attempt + 1}), "
                        f"retrying in {delay}s: {result.error}"
                    )
                    await asyncio.sleep(delay)
                    continue

            # Non-retryable or max retries reached
            return result

        return result

    async def calculate_case_score(
        self,
        case: TestCase,
        response: ChatResponse,
    ) -> CaseScore:
        """
        Calculate scores for a single case.

        Args:
            case: Test case
            response: Chat response

        Returns:
            score: Dimension scores
        """
        # Get trace detail for file usage analysis
        used_files: list[str] = []
        if response.langfuse_trace_id:
            try:
                trace_detail = await self.langfuse.get_trace_detail(
                    response.langfuse_trace_id
                )
                # Extract file operations from spans
                trace_data = {
                    "spans": [
                        {
                            "name": s.name,
                            "input": s.input,
                            "output": s.output,
                        }
                        for s in trace_detail.spans
                    ]
                }
                used_files = self.calculator.extract_file_operations(trace_data)
            except Exception as e:
                logger.warning(f"Failed to get trace detail: {e}")

        # Calculate response quality using LLM (simplified for now)
        # In production, this would call an LLM to evaluate
        response_quality = self._estimate_response_quality(
            response.content,
            case.expected_behavior,
        )

        # Calculate all scores
        return self.calculator.calculate_case_score(
            response=response.content,
            actual_skill=response.skill_used,
            expected_skill=case.expected_skill,
            expected_contains=case.expected_output_contains,
            used_files=used_files,
            expected_files=case.context_files,
            response_quality=response_quality,
        )

    def _estimate_response_quality(
        self,
        response: str,
        expected_behavior: str,
    ) -> float:
        """
        Estimate response quality.

        In production, this would use an LLM to evaluate.
        For now, use a simple heuristic.
        """
        if not response:
            return 0.0

        # Simple heuristics
        score = 0.5  # Base score

        # Length check
        if len(response) > 100:
            score += 0.1
        if len(response) > 500:
            score += 0.1

        # Check for error indicators
        error_indicators = ["抱歉", "无法", "错误", "error", "sorry", "cannot"]
        if any(indicator in response.lower() for indicator in error_indicators):
            score -= 0.2

        # Check for structure (lists, sections)
        if any(marker in response for marker in ["- ", "1.", "##", "**"]):
            score += 0.1

        return max(0.0, min(1.0, score))

    async def _write_scores_to_langfuse(
        self,
        trace_id: str,
        scores: CaseScore,
    ) -> None:
        """Write scores to Langfuse."""
        score_inputs = [
            ScoreInput(trace_id=trace_id, name="correctness", value=scores.correctness),
            ScoreInput(trace_id=trace_id, name="skill_trigger", value=scores.skill_trigger),
            ScoreInput(trace_id=trace_id, name="response_quality", value=scores.response_quality),
            ScoreInput(trace_id=trace_id, name="file_context_usage", value=scores.file_context_usage),
            ScoreInput(trace_id=trace_id, name="overall", value=scores.overall),
        ]
        await self.langfuse.add_scores_batch(score_inputs)

    def _create_failed_case(
        self,
        case: TestCase,
        result: CaseResult,
    ) -> FailedCase:
        """Create FailedCase from case result."""
        # Determine failure category
        category = self._categorize_failure(case, result)

        return FailedCase(
            case_id=case.case_id,
            actual_output=result.response.content,
            actual_skill=result.response.skill_used,
            scores=result.scores.to_dict(),
            failure_category=category,
            failure_reason=result.error or self._describe_failure(case, result),
            file_related=len(case.context_files) > 0 and result.scores.file_context_usage < 0.5,
            langfuse_trace_id=result.response.langfuse_trace_id,
        )

    def _categorize_failure(
        self,
        case: TestCase,
        result: CaseResult,
    ) -> FailureCategory:
        """Categorize failure type."""
        if result.error:
            if "Timeout" in result.error:
                return FailureCategory.TIMEOUT
            return FailureCategory.EXECUTION_ERROR

        # Skill trigger issues
        if case.expected_skill:
            if not result.response.skill_used:
                return FailureCategory.SKILL_NOT_TRIGGERED
            if result.response.skill_used != case.expected_skill:
                return FailureCategory.WRONG_SKILL_TRIGGERED

        # Output issues
        if result.scores.correctness == 0:
            return FailureCategory.OUTPUT_INCORRECT
        if result.scores.correctness < 1.0:
            return FailureCategory.OUTPUT_INCOMPLETE

        # File context issues
        if result.scores.file_context_usage < 0.5:
            return FailureCategory.FILE_CONTEXT_ERROR

        return FailureCategory.OUTPUT_INCOMPLETE

    def _describe_failure(
        self,
        case: TestCase,
        result: CaseResult,
    ) -> str:
        """Generate human-readable failure description."""
        reasons = []

        if case.expected_skill and result.response.skill_used != case.expected_skill:
            reasons.append(
                f"Expected skill '{case.expected_skill}', got '{result.response.skill_used}'"
            )

        if result.scores.correctness < 1.0:
            missing = [
                kw for kw in case.expected_output_contains
                if kw not in result.response.content
            ]
            if missing:
                reasons.append(f"Missing keywords: {missing}")

        if result.scores.file_context_usage < 0.5 and case.context_files:
            reasons.append("File context not properly used")

        return "; ".join(reasons) if reasons else "Did not meet quality threshold"
