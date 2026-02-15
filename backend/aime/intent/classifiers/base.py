"""Base class for intent classifiers."""

from abc import ABC, abstractmethod
from typing import Any

from backend.aime.intent.models import IntentResult


class ClassifierBase(ABC):
    """Abstract base class for intent classifiers.

    Classifiers are executed in priority order until one returns
    a confident result. Implementations should be stateless.

    Priority levels (lower = higher priority):
        - 0-9: Rule-based (explicit routing, skill detection)
        - 10-19: Keyword-based (pattern matching)
        - 20+: LLM-based (semantic analysis)
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
