"""Evaluation result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field


class FailureCategory(str, Enum):
    """Failure classification."""

    SKILL_NOT_TRIGGERED = "skill_not_triggered"
    WRONG_SKILL_TRIGGERED = "wrong_skill_triggered"
    OUTPUT_INCORRECT = "output_incorrect"
    OUTPUT_INCOMPLETE = "output_incomplete"
    EXECUTION_ERROR = "execution_error"
    TIMEOUT = "timeout"
    FILE_CONTEXT_ERROR = "file_context_error"


@dataclass
class CaseScore:
    """Score for a single test case."""

    correctness: float = 0.0  # [0, 1] - 50% weight
    skill_trigger: float = 0.0  # [0, 1] - 16.7% weight
    response_quality: float = 0.0  # [0, 1] - 16.7% weight
    file_context_usage: float = 0.0  # [0, 1] - 16.7% weight
    overall: float = 0.0  # Weighted average

    def calculate_overall(self) -> float:
        """Calculate weighted overall score."""
        self.overall = (
            0.50 * self.correctness
            + 0.167 * self.skill_trigger
            + 0.167 * self.response_quality
            + 0.167 * self.file_context_usage
        )
        return self.overall

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "correctness": self.correctness,
            "skill_trigger": self.skill_trigger,
            "response_quality": self.response_quality,
            "file_context_usage": self.file_context_usage,
            "overall": self.overall,
        }

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "CaseScore":
        """Create from dictionary."""
        return cls(
            correctness=data.get("correctness", 0.0),
            skill_trigger=data.get("skill_trigger", 0.0),
            response_quality=data.get("response_quality", 0.0),
            file_context_usage=data.get("file_context_usage", 0.0),
            overall=data.get("overall", 0.0),
        )


@dataclass
class ChatResponse:
    """Chat response from SunnyAgent."""

    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    agent_used: str | None = None
    skill_used: str | None = None
    langfuse_trace_id: str | None = None


@dataclass
class CaseResult:
    """Result for a single test case."""

    case_id: str
    passed: bool
    response: ChatResponse
    scores: CaseScore
    error: str | None = None
    execution_time: float = 0.0


class FailedCase(BaseModel):
    """Failed case details."""

    # Identity
    case_id: str

    # Execution details
    actual_output: str = ""
    actual_skill: str | None = None

    # Scores
    scores: dict[str, float] = Field(default_factory=dict)

    # Classification
    failure_category: FailureCategory
    failure_reason: str = ""
    file_related: bool = False

    # Tracing
    langfuse_trace_id: str | None = None
    langfuse_trace_url: str | None = None


class EvaluationResult(BaseModel):
    """Evaluation result summary."""

    # Identity
    evaluation_id: str = Field(..., description="UUID")
    dataset_name: str
    dataset_version: str
    iteration: int = 0

    # Summary
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    overall_score: float = 0.0

    # Dimension scores
    scores_by_dimension: dict[str, float] = Field(default_factory=dict)

    # Details
    failed_case_details: list[FailedCase] = Field(default_factory=list)
    passed_case_ids: list[str] = Field(default_factory=list)

    # Langfuse
    langfuse_session_id: str | None = None
    langfuse_dashboard_url: str | None = None

    # Timing
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    duration_seconds: float = 0.0

    @computed_field
    @property
    def pass_rate(self) -> float:
        """Calculate pass rate."""
        if self.total_cases == 0:
            return 0.0
        return self.passed_cases / self.total_cases

    def complete(self) -> None:
        """Mark evaluation as complete and calculate duration."""
        self.completed_at = datetime.now()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()


# Exceptions


class EvaluationError(Exception):
    """Base evaluation error."""

    pass


class CaseExecutionError(EvaluationError):
    """Case execution error."""

    def __init__(self, case_id: str, reason: str):
        self.case_id = case_id
        self.reason = reason
        super().__init__(f"Case {case_id} failed: {reason}")


class CaseTimeoutError(CaseExecutionError):
    """Case timeout error."""

    pass
