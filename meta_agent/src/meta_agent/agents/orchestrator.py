"""Orchestrator Agent - coordinates the optimization loop."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from meta_agent.agents.base import BaseAgent, AgentContext, AgentResult
from meta_agent.agents.environment_setup import EnvironmentSetupAgent
from meta_agent.agents.evaluator import EvaluatorAgent
from meta_agent.agents.analyzer import AnalyzerAgent
from meta_agent.agents.generator import GeneratorAgent
from meta_agent.agents.reviewer import ReviewerAgent
from meta_agent.models.dataset import TestDataset
from meta_agent.models.optimization import (
    OptimizationConfig,
    Checkpoint,
    OptimizationState,
    IterationReport,
)
from meta_agent.services.dataset_service import DatasetService


class OrchestratorAgent(BaseAgent[Checkpoint]):
    """Agent responsible for coordinating the optimization loop.

    Orchestrates:
    - Environment Setup -> Evaluation -> Analysis -> Generation -> Review -> Re-evaluation
    - Manages iteration state
    - Applies termination conditions
    - Handles regression detection and rollback
    """

    def __init__(
        self,
        config: OptimizationConfig,
        environment_agent: EnvironmentSetupAgent,
        evaluator_agent: EvaluatorAgent,
        analyzer_agent: AnalyzerAgent,
        generator_agent: GeneratorAgent,
        reviewer_agent: ReviewerAgent,
        dataset_service: DatasetService,
        checkpoints_dir: str,
        api_key: str | None = None,
    ):
        """
        Initialize orchestrator agent.

        Args:
            config: Optimization configuration
            environment_agent: Environment setup agent
            evaluator_agent: Evaluator agent
            analyzer_agent: Analyzer agent
            generator_agent: Generator agent
            reviewer_agent: Reviewer agent
            dataset_service: Dataset service
            checkpoints_dir: Directory for saving checkpoints
            api_key: Anthropic API key (optional)
        """
        super().__init__(
            name="Orchestrator",
            description="Coordinates the optimization loop",
            api_key=api_key,
        )
        self.config = config
        self.environment_agent = environment_agent
        self.evaluator_agent = evaluator_agent
        self.analyzer_agent = analyzer_agent
        self.generator_agent = generator_agent
        self.reviewer_agent = reviewer_agent
        self.dataset_service = dataset_service
        self.checkpoints_dir = Path(checkpoints_dir)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    async def run(self, context: AgentContext) -> AgentResult:
        """
        Run optimization loop.

        Args:
            context: Agent context

        Returns:
            Result with final Checkpoint
        """
        self.log("Starting optimization loop")

        # Load or create checkpoint
        checkpoint = self._get_or_create_checkpoint(context)
        context.optimization_id = checkpoint.optimization_id
        context.plugin_name = self.config.target_plugin
        context.project_name = self.config.test_project_name

        try:
            # Load dataset
            dataset = self.dataset_service.load_dataset(self.config.dataset_path)
            context.metadata["dataset"] = dataset

            # Setup environment
            setup_result = await self.environment_agent.run(context)
            if not setup_result.success:
                return AgentResult.fail(f"Environment setup failed: {setup_result.error}")

            # Main optimization loop
            while True:
                iteration_report = await self._run_iteration(context, checkpoint)

                # Save checkpoint
                self._save_checkpoint(checkpoint)

                # Check termination
                should_terminate, reason = self.config.should_terminate(
                    current_score=checkpoint.best_score,
                    current_iteration=checkpoint.current_iteration,
                    no_improvement_count=checkpoint.no_improvement_count,
                )

                if should_terminate:
                    self.log(f"Terminating: {reason}")
                    checkpoint.state = OptimizationState.COMPLETED
                    self._save_checkpoint(checkpoint)
                    break

                # Check for regression
                if context.evaluation_result and checkpoint.is_regression(
                    context.evaluation_result.overall_score
                ):
                    await self._handle_regression(context, checkpoint)

            return AgentResult.ok(
                message=f"Optimization complete: score={checkpoint.best_score:.2f}",
                data=checkpoint,
            )

        except Exception as e:
            self.log(f"Optimization failed: {e}", "error")
            checkpoint.state = OptimizationState.FAILED
            checkpoint.error_message = str(e)
            self._save_checkpoint(checkpoint)
            return AgentResult.fail(str(e), data=checkpoint)

        finally:
            # Cleanup
            cleanup_project = self.config.cleanup_on_complete
            await self.environment_agent.cleanup(context, delete_project=cleanup_project)

    async def _run_iteration(
        self,
        context: AgentContext,
        checkpoint: Checkpoint,
    ) -> IterationReport:
        """Run a single iteration."""
        context.iteration = checkpoint.current_iteration + 1
        self.log(f"Starting iteration {context.iteration}")

        report = IterationReport(
            iteration=context.iteration,
            optimization_id=checkpoint.optimization_id,
            score_before=checkpoint.best_score,
            score_after=0.0,
        )

        # 1. Evaluate
        eval_result = await self.evaluator_agent.run(context)
        if not eval_result.success:
            report.decision = "terminate"
            report.decision_reason = f"Evaluation failed: {eval_result.error}"
            return report

        evaluation = context.evaluation_result
        report.score_after = evaluation.overall_score
        report.evaluation_id = evaluation.evaluation_id
        report.langfuse_evaluation_url = evaluation.langfuse_dashboard_url

        # Update checkpoint with score
        checkpoint.update_progress(evaluation.overall_score, evaluation.evaluation_id)

        # Check if already at target
        if evaluation.overall_score >= self.config.target_score:
            report.decision = "terminate"
            report.decision_reason = "Target score reached"
            report.complete()
            return report

        # 2. Analyze failures
        if evaluation.failed_cases > 0:
            analyze_result = await self.analyzer_agent.run(context)
            if analyze_result.success and context.analysis_result:
                report.analysis_summary = context.analysis_result.summary

                # 3. Generate modifications
                gen_result = await self.generator_agent.run(context)
                if gen_result.success and context.generation_result:
                    # 4. Review changes
                    review_result = await self.reviewer_agent.run(context)
                    if review_result.success:
                        review_data = review_result.data
                        if review_data and review_data.all_approved:
                            # Record modifications
                            for change in context.generation_result.changes:
                                checkpoint.add_file_modification(
                                    file_path=change.file_path,
                                    modification_type=change.change_type,
                                    git_commit_hash=change.git_commit_hash,
                                )
                                report.modifications.append(
                                    checkpoint.modified_files[-1]
                                )
                        else:
                            self.log("Changes not approved by reviewer", "warning")

        report.decision = "continue"
        report.complete()
        return report

    async def _handle_regression(
        self,
        context: AgentContext,
        checkpoint: Checkpoint,
    ) -> None:
        """Handle regression by rolling back."""
        self.log("Regression detected, rolling back", "warning")

        # Get the last modification
        if checkpoint.modified_files:
            last_modification = checkpoint.modified_files[-1]

            # Try to rollback
            from meta_agent.agents.generator import FileChange

            change = FileChange(
                file_path=last_modification.file_path,
                change_type=last_modification.modification_type,
                description="Regression rollback",
                git_commit_hash=last_modification.git_commit_hash,
            )

            success = await self.generator_agent.rollback_change(change)
            if success:
                checkpoint.state = OptimizationState.ROLLED_BACK
                self.log("Rollback successful")
            else:
                self.log("Rollback failed", "error")

    def _get_or_create_checkpoint(self, context: AgentContext) -> Checkpoint:
        """Get existing checkpoint or create new one."""
        # Check for existing checkpoint to resume
        if context.optimization_id:
            checkpoint_file = self.checkpoints_dir / f"{context.optimization_id}.json"
            if checkpoint_file.exists():
                with open(checkpoint_file) as f:
                    data = json.load(f)
                    return Checkpoint(**data)

        # Create new checkpoint
        return Checkpoint(
            optimization_id=str(uuid.uuid4()),
            config=self.config,
            state=OptimizationState.IN_PROGRESS,
        )

    def _save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to file."""
        checkpoint.updated_at = datetime.now()
        checkpoint_file = self.checkpoints_dir / f"{checkpoint.optimization_id}.json"

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint.model_dump(mode="json"), f, indent=2, default=str)

        self.log(f"Saved checkpoint: {checkpoint.optimization_id[:8]}", "debug")

    @classmethod
    def load_checkpoint(cls, checkpoint_id: str, checkpoints_dir: str) -> Checkpoint | None:
        """Load checkpoint from file."""
        checkpoint_file = Path(checkpoints_dir) / f"{checkpoint_id}.json"
        if not checkpoint_file.exists():
            return None

        with open(checkpoint_file) as f:
            data = json.load(f)
            return Checkpoint(**data)

    @classmethod
    def list_checkpoints(cls, checkpoints_dir: str) -> list[dict[str, Any]]:
        """List all checkpoints."""
        checkpoints = []
        checkpoints_path = Path(checkpoints_dir)

        if not checkpoints_path.exists():
            return checkpoints

        for f in checkpoints_path.glob("*.json"):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    checkpoints.append({
                        "id": data.get("optimization_id", f.stem),
                        "plugin": data.get("config", {}).get("target_plugin", "unknown"),
                        "iteration": data.get("current_iteration", 0),
                        "best_score": data.get("best_score", 0.0),
                        "state": data.get("state", "unknown"),
                        "updated_at": data.get("updated_at", ""),
                    })
            except Exception:
                pass

        return sorted(checkpoints, key=lambda x: x.get("updated_at", ""), reverse=True)
