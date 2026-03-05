"""Data models for Meta-Agent system."""

from meta_agent.models.dataset import (
    TestDataset,
    TestCase,
    TestFile,
    Message,
    ProjectConfig,
)
from meta_agent.models.evaluation import (
    EvaluationResult,
    CaseResult,
    CaseScore,
    FailedCase,
    FailureCategory,
)
from meta_agent.models.optimization import (
    OptimizationConfig,
    Checkpoint,
    OptimizationState,
    FileModification,
    IterationReport,
)
from meta_agent.models.plugin import (
    Command,
    CommandFrontmatter,
    Skill,
    SkillFrontmatter,
)

__all__ = [
    # Dataset
    "TestDataset",
    "TestCase",
    "TestFile",
    "Message",
    "ProjectConfig",
    # Evaluation
    "EvaluationResult",
    "CaseResult",
    "CaseScore",
    "FailedCase",
    "FailureCategory",
    # Optimization
    "OptimizationConfig",
    "Checkpoint",
    "OptimizationState",
    "FileModification",
    "IterationReport",
    # Plugin
    "Command",
    "CommandFrontmatter",
    "Skill",
    "SkillFrontmatter",
]
