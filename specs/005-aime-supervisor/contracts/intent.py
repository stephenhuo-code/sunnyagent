"""Intent Module Contracts

Defines interfaces for intent analysis components.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

# =============================================================================
# Type Definitions
# =============================================================================

Action = Literal["direct_reply", "delegate", "plan", "clarify"]
"""
Action types that determine Planner behavior:
- direct_reply: Simple question, respond directly
- delegate: Single task, route to specialist agent
- plan: Complex task, decompose into subtasks
- clarify: Unclear intent, ask for clarification
"""


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class IntentResult:
    """Result of intent analysis.

    Attributes:
        action: The determined action type
        confidence: Confidence score (0.0-1.0)
        capabilities: Required capabilities for agent matching
        domain: Domain identifier (for future extension)
        clarify_questions: Questions to ask when action is 'clarify'
    """

    action: Action
    confidence: float = 0.0
    capabilities: list[str] = field(default_factory=list)
    domain: str = "general"
    clarify_questions: list[str] | None = None


# =============================================================================
# Abstract Base Classes
# =============================================================================


class ClassifierBase(ABC):
    """Abstract base class for intent classifiers.

    Classifiers are executed in priority order until one returns
    a confident result. Implementations should be stateless.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Classifier name for logging and debugging."""
        ...

    @property
    @abstractmethod
    def priority(self) -> int:
        """Execution priority (lower = higher priority)."""
        ...

    @abstractmethod
    async def classify(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        domain: str | None = None,
    ) -> IntentResult | None:
        """Classify user intent.

        Args:
            message: User message to classify
            context: Optional conversation context
            domain: Optional domain hint

        Returns:
            IntentResult if classification is confident, None to pass to next classifier
        """
        ...


class DomainRecognizer(ABC):
    """Abstract base class for domain recognizers.

    Domain recognizers identify specialized domains (e.g., manufacturing, quality)
    to enrich context for classifiers.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Recognizer name."""
        ...

    @property
    @abstractmethod
    def supported_domains(self) -> list[str]:
        """List of domains this recognizer can identify."""
        ...

    @abstractmethod
    def recognize(self, message: str) -> str | None:
        """Recognize domain from message.

        Args:
            message: User message

        Returns:
            Domain identifier if recognized, None otherwise
        """
        ...


class IntentAnalyzerProtocol(ABC):
    """Protocol for intent analyzer implementations.

    The analyzer orchestrates multiple classifiers and domain recognizers
    to determine user intent.
    """

    @abstractmethod
    async def analyze(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> IntentResult:
        """Analyze user message and determine intent.

        Args:
            message: User message
            context: Optional conversation context

        Returns:
            IntentResult with action and supporting information
        """
        ...
