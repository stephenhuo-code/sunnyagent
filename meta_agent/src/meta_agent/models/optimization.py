"""Optimization configuration and checkpoint models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class OptimizationState(str, Enum):
    """Optimization state."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class FileModification(BaseModel):
    """File modification record."""

    file_path: str
    modification_type: Literal["create", "update"]
    git_commit_hash: str = ""
    iteration: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)


class OptimizationConfig(BaseModel):
    """Optimization configuration."""

    # Target
    target_plugin: str = Field(..., description="Target plugin name")
    dataset_path: str = Field(..., description="Dataset file path")

    # Completion criteria (with defaults)
    target_score: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Target score (0-1), optimization stops when reached",
    )
    max_iterations: int = Field(
        default=5,
        ge=1,
        description="Maximum iterations to prevent infinite optimization",
    )
    regression_threshold: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Regression threshold, triggers rollback when score drops by this amount",
    )
    patience: int = Field(
        default=2,
        ge=1,
        description="Patience value, early termination after this many rounds without improvement",
    )
    min_improvement: float = Field(
        default=0.02,
        ge=0.0,
        le=1.0,
        description="Minimum effective improvement, below this is considered no improvement",
    )

    # Execution
    test_project_name: str = "meta-agent-test"
    cleanup_on_complete: bool = False

    # Git
    auto_commit: bool = True
    commit_prefix: str = "meta-agent:"

    @field_validator("target_score")
    @classmethod
    def validate_target_score(cls, v: float) -> float:
        """Validate target_score is between 0 and 1."""
        if not 0 < v <= 1:
            raise ValueError("target_score must be between 0 and 1")
        return v

    def should_terminate(
        self,
        current_score: float,
        current_iteration: int,
        no_improvement_count: int,
    ) -> tuple[bool, str]:
        """
        Check if optimization should terminate.

        Returns:
            (should_terminate, reason)
        """
        # Check if target reached
        if current_score >= self.target_score:
            return True, f"Target score {self.target_score} reached"

        # Check if max iterations reached
        if current_iteration >= self.max_iterations:
            return True, f"Max iterations {self.max_iterations} reached"

        # Check patience
        if no_improvement_count >= self.patience:
            return True, f"No improvement for {self.patience} consecutive iterations"

        return False, ""


class Checkpoint(BaseModel):
    """Optimization checkpoint for resume support."""

    # Identity
    optimization_id: str = Field(..., description="UUID")

    # Config snapshot
    config: OptimizationConfig

    # Progress
    current_iteration: int = 0
    best_score: float = 0.0
    best_iteration: int = 0
    last_evaluation_id: str | None = None
    no_improvement_count: int = 0

    # Score history
    score_history: list[float] = Field(default_factory=list)

    # File tracking
    modified_files: list[FileModification] = Field(default_factory=list)

    # State
    state: OptimizationState = OptimizationState.PENDING
    error_message: str | None = None

    # Timing
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def update_progress(
        self,
        score: float,
        evaluation_id: str,
    ) -> None:
        """Update progress after an iteration."""
        self.current_iteration += 1
        self.score_history.append(score)
        self.last_evaluation_id = evaluation_id
        self.updated_at = datetime.now()

        # Check improvement
        if score > self.best_score + self.config.min_improvement:
            self.best_score = score
            self.best_iteration = self.current_iteration
            self.no_improvement_count = 0
        else:
            self.no_improvement_count += 1

    def is_regression(self, new_score: float) -> bool:
        """Check if new score indicates regression."""
        if not self.score_history:
            return False
        last_score = self.score_history[-1]
        return (last_score - new_score) > self.config.regression_threshold

    def add_file_modification(
        self,
        file_path: str,
        modification_type: Literal["create", "update"],
        git_commit_hash: str = "",
    ) -> None:
        """Record a file modification."""
        self.modified_files.append(
            FileModification(
                file_path=file_path,
                modification_type=modification_type,
                git_commit_hash=git_commit_hash,
                iteration=self.current_iteration,
            )
        )
        self.updated_at = datetime.now()


class IterationReport(BaseModel):
    """Single iteration report."""

    # Identity
    iteration: int
    optimization_id: str

    # Scores
    score_before: float
    score_after: float
    score_delta: float = 0.0

    # Actions taken
    modifications: list[FileModification] = Field(default_factory=list)
    analysis_summary: str = ""

    # Evaluation
    evaluation_id: str = ""
    langfuse_evaluation_url: str | None = None

    # Decision
    decision: Literal["continue", "rollback", "terminate"] = "continue"
    decision_reason: str = ""

    # Timing
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None

    def complete(self) -> None:
        """Mark iteration as complete."""
        self.completed_at = datetime.now()
        self.score_delta = self.score_after - self.score_before
