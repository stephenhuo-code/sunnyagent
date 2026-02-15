"""Intent Analyzer - orchestrates classifier chain for intent analysis."""

import logging
from typing import Any

from backend.aime.intent.classifiers.base import ClassifierBase
from backend.aime.intent.classifiers.keyword_based import KeywordClassifier
from backend.aime.intent.classifiers.llm_based import LLMClassifier
from backend.aime.intent.classifiers.rule_based import RuleBasedClassifier
from backend.aime.intent.models import IntentResult

logger = logging.getLogger(__name__)


class IntentAnalyzer:
    """Orchestrates intent analysis through classifier chain.

    Classifiers are executed in priority order (lower priority = higher precedence):
    1. RuleBasedClassifier (priority=0) - Explicit routing patterns
    2. KeywordClassifier (priority=10) - Quick pattern matching
    3. LLMClassifier (priority=20) - Semantic analysis

    Each classifier returns IntentResult or None. First non-None result is used.
    If all classifiers return None, defaults to direct_reply with low confidence.
    """

    def __init__(self, classifiers: list[ClassifierBase] | None = None):
        """Initialize with classifier chain.

        Args:
            classifiers: Optional custom classifiers. If None, uses default chain.
        """
        if classifiers is None:
            # Default classifier chain with all three classifiers
            classifiers = [
                RuleBasedClassifier(),
                KeywordClassifier(),
                LLMClassifier(),
            ]

        # Sort by priority (lower = higher precedence)
        self._classifiers = sorted(classifiers, key=lambda c: c.priority)
        logger.info(
            f"IntentAnalyzer initialized with classifiers: "
            f"{[c.name for c in self._classifiers]}"
        )

    def add_classifier(self, classifier: ClassifierBase) -> None:
        """Add a classifier to the chain.

        Args:
            classifier: Classifier to add
        """
        self._classifiers.append(classifier)
        self._classifiers.sort(key=lambda c: c.priority)
        logger.info(f"Added classifier: {classifier.name}")

    async def analyze(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> IntentResult:
        """Analyze user message and determine intent.

        Runs classifiers in priority order until one returns a confident result.

        Args:
            message: User message
            context: Optional conversation context (may contain explicit_agent, etc.)

        Returns:
            IntentResult with determined action and supporting information
        """
        # Log entry with message preview and context summary
        context_summary = {k: v for k, v in (context or {}).items() if v is not None}
        logger.info(
            f"[analyze] Starting - message_len={len(message)}, "
            f"preview='{message[:50]}...', context={context_summary}"
        )

        domain = context.get("domain") if context else None

        for classifier in self._classifiers:
            try:
                result = await classifier.classify(
                    message=message,
                    context=context,
                    domain=domain,
                )
                if result is not None:
                    logger.debug(
                        f"Intent classified by {classifier.name}: "
                        f"action={result.action}, confidence={result.confidence}"
                    )
                    return result
            except Exception as e:
                logger.warning(f"Classifier {classifier.name} failed: {e}")
                continue

        # No classifier matched - default to direct_reply with low confidence
        # This allows simple unmatched queries to get direct responses
        logger.debug("No classifier matched, defaulting to direct_reply")
        return IntentResult(
            action="direct_reply",
            confidence=0.3,
            domain=domain or "general",
        )
